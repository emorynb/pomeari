from datetime import datetime
from random import randint
from collections.abc import Mapping
from typing import Any

from frontmatter import Post

from pomeari.platforms.base import Platform
from pomeari.types import ModuleInfo, XpostResult


class LongBlankPlatform(Platform):
    info = ModuleInfo(title="Long&Blank")

    async def post_long(self, post: Post, config: Mapping[str, Any]) -> XpostResult:
        id = "".join(["{}".format(randint(0, 9)) for num in range(0, 10)])
        created_at = datetime.today().isoformat()
        return XpostResult(url=f"https://longblank.local/{id}", created_at=created_at)
