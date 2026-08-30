from frontmatter import Post
from collections.abc import Mapping

from pomeari.platforms.base import Platform
from pomeari.types import ModuleInfo, PlatformConfig, XpostResult


class ShortPlatform(Platform):
    info = ModuleInfo(title="Short platform")

    def __init__(self, url: str = "https://short.example/post"):
        self.url = url
        self.posts = []

    async def post_short(self, content: str, config: Mapping[str, str]) -> XpostResult:
        self.posts.append((content, config))
        return XpostResult(url=self.url)


class ConfiguredShortPlatform(ShortPlatform):
    info = ModuleInfo(
        title="Configured short platform",
        config_keys=[
            PlatformConfig(
                key="short_token",
                description="test token",
                required=True,
            )
        ],
    )


class ConfigUpdatingPlatform(Platform):
    info = ModuleInfo(
        title="Config-updating platform",
        config_keys=[
            PlatformConfig(
                key="untouched",
                description="an unchanged value",
                required=True,
            ),
            PlatformConfig(
                key="replaced",
                description="a replaced value",
                required=True,
            ),
            PlatformConfig(
                key="added",
                description="a newly persisted value",
                default="default",
            ),
        ],
    )

    def __init__(self):
        self.posts = []

    def _result(self) -> XpostResult:
        return XpostResult(
            url="https://config-updating.example/post",
            config_update={"replaced": "new", "added": "added"},
        )

    async def post_short(self, content: str, config: Mapping[str, str]) -> XpostResult:
        self.posts.append((content, config))
        return self._result()

    async def post_long(self, post: Post, config: Mapping[str, str]) -> XpostResult:
        self.posts.append((post, config))
        return self._result()


class LongPlatform(Platform):
    info = ModuleInfo(title="Long platform")

    def __init__(self, url: str = "https://long.example/post"):
        self.url = url
        self.posts = []

    async def post_long(self, post: Post, config: Mapping[str, str]) -> XpostResult:
        self.posts.append((post, config))
        return XpostResult(url=self.url)


class FailingLongPlatform(Platform):
    info = ModuleInfo(title="Failing long platform")

    async def post_long(self, post: Post, config: Mapping[str, str]) -> XpostResult:
        raise RuntimeError("primary platform rejected the post")
