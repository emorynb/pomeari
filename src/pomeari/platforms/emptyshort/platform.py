from datetime import datetime
from random import randint
from typing import Any

from frontmatter import Post

from pomeari.platforms.base import Platform
from pomeari.types import ModuleInfo, XpostResult


class EmptyShortPlatform(Platform):
    info = ModuleInfo(title="EmptyShort")

    async def post_short(self, content: str, config: dict[str, Any]) -> XpostResult:
        id = "".join(["{}".format(randint(0, 9)) for num in range(0, 12)])
        created_at = datetime.today().isoformat()
        return XpostResult(url=f"https://emptyshort.local/{id}", created_at=created_at)

    async def post_long(self, post: Post, config: dict[str, Any]) -> XpostResult:
        raise NotImplementedError
