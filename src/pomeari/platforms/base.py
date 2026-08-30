from abc import ABC
from collections.abc import Mapping

from frontmatter import Post

from ..types import ModuleInfo, XpostResult


class Platform(ABC):  # no real reason to inherit from ABC here but whatever
    info: ModuleInfo

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "info"):
            raise TypeError(f"{cls.__name__} must define class attribute `info`")

        base = Platform

        def _overridden(name: str) -> bool:
            return getattr(cls, name) is not getattr(base, name)

        if not (_overridden("post_short") or _overridden("post_long")):
            raise TypeError(
                f"{cls.__name__} must override at least one of `post_short` or `post_long`"
            )

    def supports_post_long(self) -> bool:
        return type(self).post_long is not Platform.post_long

    def supports_post_short(self) -> bool:
        return type(self).post_short is not Platform.post_short

    async def post_short(self, content: str, config: Mapping[str, str]) -> XpostResult:
        raise NotImplementedError

    async def post_long(self, post: Post, config: Mapping[str, str]) -> XpostResult:
        raise NotImplementedError

    async def close(self):
        pass
