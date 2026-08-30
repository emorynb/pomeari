import asyncio
from collections.abc import Iterable, Mapping
from pathlib import Path

from .db import (
    DEFAULT_DATA_DIR,
    DEFAULT_DB_PATH,
    LEGACY_DB_PATH,
    Database,
    prepare_data_dir,
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
    """The central async façade over all the features offered by Pomeari.

    Intended to be used in a context manager:

        async with PomeariService() as service:
            ...

    Entering initializes storage and discovers adapters; exiting invokes
    platform cleanup.

    The constructor accepts the following arguments used for testing/embedding
    (all optional):

    - ``data_dir``: custom data directory.
    - ``platforms``: injected ``Platform`` mapping.
    """

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
        """Execute the service initialization steps.

        Runs automatically when entering the context manager.
        """

        prepare_data_dir(self.data_dir, self._legacy_db_path)
        await self.database.initialize()
        self.drafts.initialize()

        if not self._platforms:
            self._platforms = discover_platforms()

    def _available_platforms(self) -> Mapping[str, Platform]:
        if not self._platforms:
            raise RuntimeError("PomeariService.initialize() must be called first.")
        return self._platforms

    async def list_platforms(self) -> Iterable[PlatformInfo]:
        """List all of the available adapters.

        See ``PlatformInfo`` for what information is included.
        """

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

    async def get_config(self) -> Mapping[str, str]:
        """Load all persisted platform configuration as a mapping."""

        return await self.database.load_config()

    async def set_config(self, key: str, value: str):
        """Create or replace a persisted configuration entry."""

        await self.database.set_config(key, value)

    async def remove_config(self, key: str):
        """Remove a configuration entry.

        Removing an absent key is harmless at the database level, so no guards
        are necessary for that.
        """

        await self.database.remove_config(key)

    async def clear_config(self):
        """Remove all persisted platform configuration entries."""

        await self.database.clear_config()

    async def get_favorite_platform(self) -> str:
        """Return the registered name of the persisted favorite platform.

        A newly initialized database defaults this value to ``mastodon``.
        """

        return await self.database.get_favorite_platform()

    async def set_favorite_platform(self, name: str):
        """Persist a new favorite platform after verifying that it is currently
        available; raise ``PlatformNotFoundError`` otherwise.
        """

        if name not in self._available_platforms():
            raise PlatformNotFoundError(name)
        await self.database.set_favorite_platform(name)

    async def publish(self, request: PublishRequest) -> PublishResult:
        """Process a ``PublishRequest``.

        This method loads current configuration and the favorite platform,
        delegates orchestration to ``publish_to_platforms``, records the run,
        and returns an aggregate ``PublishResult``.

        Expected validation failures use exceptions from ``pomeari.errors``.
        Individual adapter failures are represented in the returned per-platform
        results.
        """

        config = await self.database.load_config()
        favorite_name = await self.database.get_favorite_platform()
        return await publish_to_platforms(
            request=request,
            platforms=self._available_platforms(),
            favorite_name=favorite_name,
            config=config,
            database=self.database,
        )

    async def get_history(self, limit: int = 100) -> Iterable[RunLog]:
        """Return the most recent persisted publishing runs, newest first.

        Each ``RunLog`` contains its associated ``PostLog`` records.
        """

        return await self.database.get_history(limit)

    async def clear_history(self):
        """Delete all run and post logs and reset the run counter."""

        await self.database.clear_logs()

    async def reset_database(self):
        """Delete and recreate the local Pomeari database.

        This resets configuration, history, counters, and the favorite platform
        to their defaults. Drafts are untouched as they use plain file storage.
        """

        await self.database.reset()

    async def save_draft(self, draft: Draft):
        """Write or replace a ``Draft`` in local draft storage.

        Note that even though this method is async to keep the service interface
        consistent, the underlying filesystem operation is very much
        synchronous.
        """

        self.drafts.save(draft)

    async def load_draft(self, name: str) -> Draft:
        """Load a draft by ``name`` from the local storage.

        Raise a ``DraftError`` (or its derivative) if the name or stored data is
        invalid or the draft does not exist.
        """

        return self.drafts.load(name)

    async def list_drafts(self) -> Iterable[DraftSummary]:
        """Return ``DraftSummary`` objects listing all of the valid locally
        stored drafts.
        """

        return self.drafts.list()

    async def delete_draft(self, name: str):
        """Delete a draft by ``name`` from the local storage.

        Raise ``DraftNotFoundError`` if that draft cannot be located in the
        storage.
        """

        self.drafts.delete(name)

    async def close(self):
        """Close all platform adapter connections.

        Runs automatically when leaving the context manager.
        """

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
