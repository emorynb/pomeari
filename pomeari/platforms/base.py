from abc import ABC
from collections.abc import Mapping

from frontmatter import Post

from ..types import ModuleInfo, XpostResult


class Platform(ABC):  # no real reason to inherit from ABC here but whatever
    """Base class and interface for a Pomeari platform adapter.

    Subclasses must publish their adapter metadata as an ``info`` class
    attribute containing a ``ModuleInfo`` instance. They must also override at
    least one of ``post_short`` or ``post_long``; defining neither causes class
    creation to fail.

    Posting methods receive only the configuration entries declared by the
    adapter, with applicable defaults already filled in. Adapters that retain
    clients or other resources should also override ``close`` to release them.
    """

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
        """Return whether this adapter implements long-form publishing."""

        return type(self).post_long is not Platform.post_long

    def supports_post_short(self) -> bool:
        """Return whether this adapter implements short-form publishing."""

        return type(self).post_short is not Platform.post_short

    async def post_short(self, content: str, config: Mapping[str, str]) -> XpostResult:
        """Publish short-form ``content`` using the supplied platform ``config``.

        Implementations should return an ``XpostResult`` describing the created
        post. The default method raises ``NotImplementedError`` so callers may
        also use it to represent an unsupported post form.
        """

        raise NotImplementedError

    async def post_long(self, post: Post, config: Mapping[str, str]) -> XpostResult:
        """Publish a parsed long-form ``post`` using the supplied platform
        ``config``.

        The ``frontmatter.Post`` contains both the article body and any parsed
        metadata. Implementations should return an ``XpostResult`` describing
        the created post. The default method raises ``NotImplementedError`` so
        callers may also use it to represent an unsupported post form.
        """

        raise NotImplementedError

    async def close(self):
        """Release resources retained by the platform adapter.

        The default implementation does nothing. Adapters that do not keep
        connections or similar resources open do not need to implement this
        method.
        """

        pass
