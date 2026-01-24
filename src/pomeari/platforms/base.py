from abc import ABC, abstractmethod

from frontmatter import Post

from ..types import ModuleInfo, XpostResult


class Platform(ABC):
    info: ModuleInfo

    @abstractmethod
    async def post_short(self, content: str, config: dict[str, str]) -> XpostResult:
        raise NotImplementedError

    @abstractmethod
    async def post_long(self, post: Post, config: dict[str, str]) -> XpostResult:
        raise NotImplementedError
