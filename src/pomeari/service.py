import asyncio
from collections.abc import Mapping
from pathlib import Path

from .db import (
    DEFAULT_DATA_DIR,
    DEFAULT_DB_PATH,
    LEGACY_DB_PATH,
    Database,
    prepare_data_directory,
)
from .drafts import DraftStore
from .ep import discover_platforms
from .errors import PlatformNotFoundError
from .platforms.base import Platform
from .posts import publish_to_platforms
from .types import (
    Draft,
    DraftSummary,
    PlatformInfo,
    PublishRequest,
    PublishResult,
    RunLog,
)


class PomeariService:
    def __init__(
        self,
        data_dir: Path | None = None,
        platforms: Mapping[str, Platform] | None = None,
        legacy_db_path: Path | None = None,
    ):
        uses_default_data_dir = data_dir is None
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_dir = self.data_dir.expanduser()

        if legacy_db_path:
            self._legacy_db_path = legacy_db_path.expanduser()
        elif uses_default_data_dir:
            self._legacy_db_path = LEGACY_DB_PATH
        else:
            self._legacy_db_path = None

        self.database = Database(self.data_dir / DEFAULT_DB_PATH.name)
        self.drafts = DraftStore(self.data_dir / "drafts")
        self._platforms = dict(platforms) if platforms else None
        self._closed = False

    async def initialize(self):
        prepare_data_directory(self.data_dir, self._legacy_db_path)
        await self.database.initialize()
        self.drafts.initialize()

        if not self._platforms:
            self._platforms = discover_platforms()

    def _available_platforms(self) -> dict[str, Platform]:
        if not self._platforms:
            raise RuntimeError("PomeariService.initialize() must be called first.")
        return self._platforms

    async def list_platforms(self) -> list[PlatformInfo]:
        config = await self.database.load_config()
        platform_infos = []

        for name, platform in self._available_platforms().items():
            configured = True
            for entry in platform.info.config_keys:
                needs_value = entry.required or entry.default is None
                if needs_value and entry.key not in config:
                    configured = False
                    break

            platform_infos.append(
                PlatformInfo(
                    name=name,
                    module=platform.info,
                    supports_short=platform.supports_post_short(),
                    supports_long=platform.supports_post_long(),
                    configured=configured,
                )
            )

        return platform_infos

    async def get_config(self) -> dict[str, str]:
        return await self.database.load_config()

    async def set_config(self, key: str, value: str):
        await self.database.set_config(key, value)

    async def remove_config(self, key: str):
        await self.database.remove_config(key)

    async def clear_config(self):
        await self.database.clear_config()

    async def get_favorite_platform(self) -> str:
        return await self.database.get_favorite_platform()

    async def set_favorite_platform(self, name: str):
        if name not in self._available_platforms():
            raise PlatformNotFoundError(name)
        await self.database.set_favorite_platform(name)

    async def publish(self, request: PublishRequest) -> PublishResult:
        config = await self.database.load_config()
        favorite_name = await self.database.get_favorite_platform()
        return await publish_to_platforms(
            request=request,
            platforms=self._available_platforms(),
            favorite_name=favorite_name,
            config=config,
            database=self.database,
        )

    async def get_history(self, limit: int = 100) -> list[RunLog]:
        return await self.database.get_history(limit)

    async def clear_history(self):
        await self.database.clear_logs()

    async def reset_database(self):
        await self.database.reset()

    async def save_draft(self, draft: Draft):
        self.drafts.save(draft)

    async def load_draft(self, name: str) -> Draft:
        return self.drafts.load(name)

    async def list_drafts(self) -> list[DraftSummary]:
        return self.drafts.list()

    async def delete_draft(self, name: str):
        self.drafts.delete(name)

    async def close(self):
        if self._closed:
            return

        await asyncio.gather(
            *(platform.close() for platform in self._available_platforms().values()),
            return_exceptions=True,
        )
        self._closed = True

    async def __aenter__(self) -> "PomeariService":
        await self.initialize()
        return self

    async def __aexit__(self, *_args):
        await self.close()
