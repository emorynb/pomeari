from datetime import datetime
from random import randint
from typing import Any

from frontmatter import Post

from pomeari.platforms.base import Platform
from pomeari.types import ModuleInfo, XpostResult


class LongBlankPlatform(Platform):
    info = ModuleInfo(title="Long&Blank")

    async def post_short(self, content: str, config: dict[str, Any]) -> XpostResult:
        raise NotImplementedError

    async def post_long(self, post: Post, config: dict[str, Any]) -> XpostResult:
        print(post)
        print(post.metadata)
        id = "".join(["{}".format(randint(0, 9)) for num in range(0, 10)])
        created_at = datetime.today().isoformat()
        return XpostResult(url=f"https://longblank.local/{id}", created_at=created_at)
