"""
Mastodon platform module for Pomeari.

Comes built-in with Pomeari itself intentionally to give an example for how
entry points are used (see root-level pomeari `pyproject.toml`) and other code
is supposed to be written, as Mastodon gives a very simple and pleasant API for
such demonstrations. That being said, this is perfectly good for everyday usage.
All other platform modules should be placed in external packages.
"""

from datetime import datetime
from collections.abc import Mapping
from typing import Any

from httpx import AsyncClient

from pomeari.platforms.base import Platform
from pomeari.types import ModuleInfo, PlatformConfig, XpostResult


class MastodonPlatform(Platform):
    info = ModuleInfo(
        title="Mastodon",
        config_keys=[
            PlatformConfig(
                key="mastodon_instance",
                description="Mastodon instance URL",
                required=True,
            ),
            PlatformConfig(
                key="mastodon_token", description="Mastodon API token", required=True
            ),
            PlatformConfig(
                key="mastodon_supports_markdown",
                description=(
                    "Does the Mastodon instance specified support formatting posts with Markdown? "
                    "(optional, 'true'/'false', default 'false')"
                ),
                default="false",
            ),
        ],
    )

    def __init__(self) -> None:
        self._client = AsyncClient(timeout=10)

    async def post_short(self, content: str, config: Mapping[str, Any]) -> XpostResult:
        url = f"{config['mastodon_instance']}/api/v1/statuses"
        headers = {
            "Authorization": f"Bearer {config['mastodon_token']}",
            "Content-Type": "application/json",
        }

        if bool(config["mastodon_supports_markdown"]):
            status = content
        else:
            from mistletoe.block_token import Document

            from pomeari.render import PlaintextRenderer

            with PlaintextRenderer() as renderer:
                status = renderer.render(Document(content))

        resp = await self._client.post(url, headers=headers, json={"status": status})
        resp.raise_for_status()
        data = resp.json()
        # data = {
        #     "url": "https://mastodon.social/000000000000",
        #     "created_at": datetime.today().isoformat(),
        # }

        created_at = datetime.fromisoformat(
            data["created_at"].replace("Z", "+00:00")
        ).isoformat()

        return XpostResult(url=data["url"], created_at=created_at)

    async def close(self):
        await self._client.aclose()
