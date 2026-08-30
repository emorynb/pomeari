"""Collection of types that Pomeari uses to represent platforms, posts, logs,
drafts, and run results.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import NamedTuple


class PostForm(StrEnum):
    """Dictates what a post is in terms of its length.

    A short-form post is (in its broadest sense) a tweet, usually not more than
    200 characters long, oftentimes lacking any formatting.

    A long-form post is a blog post, a culinary article, or a study, commonly
    a few thousand characters long and heavily formatted with headings and
    subheadings for readability."""

    SHORT = auto()  # "i just shat my pants get ratio'd"
    LONG = auto()  # Why I Am The Golden God (11-page guide to superior life forms)"


class PlatformConfig(NamedTuple):
    """Representation of a config entry required by a ``Platform``-implementing
    module.

    - ``key`` is the stored configuration name.
    - ``description`` describes what the config is needed for.
    - ``required`` defines whether it's optional or not.
    - ``default`` provides a fallback value when applicable.

    Note that the values are represented as strings; it's on the adapters to
    validate and parse them.
    """

    key: str
    description: str
    required: bool = False
    default: str | None = None


@dataclass(slots=True)
class ModuleInfo:
    """Metadata published by a ``Platform`` implementation.

    - ``title`` supplies a human-readable platform name (falls back to the
      technical name of the module).
    - ``config_keys`` defines the recognized configuration.
    """

    title: str | None = None
    config_keys: list[PlatformConfig] = field(default_factory=list)


@dataclass
class XpostResult:
    """The successful result returned by a ``Platform`` implementation when
    posting.

    - ``url`` links to the published post.
    - ``created_at`` records its creation time (optional).
    - ``config_update`` overrides supplied keys of the platform configuration,
      for when such changes may be discovered during publishing (optional).
    - ``metadata`` stores platform-specific information for later persistence
      (optional).

    The format of ``metadata`` is not enforced by Pomeari. However, it's
    recommended that you document its format and keep it deterministic for
    future parsing (and your own sake).
    """

    url: str
    created_at: str | None = None
    config_update: dict = field(default_factory=dict)
    metadata: str | None = None


class PublishStatus(StrEnum):
    """Describes a ``Platform``'s outcome within a publishing run:

    - ``SUCCESS``: a post was published.
    - ``FAILED``: publishing was attempted but did not succeed.
    - ``SKIPPED``: no publishing attempt was made for that platform.
    """

    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass(frozen=True, slots=True)
class PublishRequest:
    """An immutable request passed to ``PomeariService``.

    - ``post_form``: long or short.
    - ``content``: full text of the post.
    - ``targets``: list of platforms to publish to (falls back to all).
    """

    post_form: PostForm
    content: str
    targets: Iterable[str] | None = None


@dataclass(frozen=True, slots=True)
class PlatformPublishResult:
    """
    Representation of a per-platform post publishing result.
    """

    platform: str
    title: str
    status: PublishStatus
    result: XpostResult | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PublishResult:
    """
    Representation of a per-run post publishing result.
    """

    run_id: int
    caption: str
    platforms: list[PlatformPublishResult]


@dataclass(frozen=True, slots=True)
class PlatformInfo:
    """A service-facing view of a discovered ``Platform``.

    - ``name``: its registered name.
    - ``module``: see ``ModuleInfo``.
    - ``supports_short``: indicates whether it supports short-form posts.
    - ``supports_long``: ditto for long-form posts.
    - ``configured``: indicates whether required configuration is currently
      available.
    """

    name: str
    module: ModuleInfo
    supports_short: bool
    supports_long: bool
    configured: bool


@dataclass(frozen=True, slots=True)
class PostLog:
    """
    Representation of a post log entry.
    """

    platform: str
    url: str
    created_at: str | None
    metadata: str | None


@dataclass(frozen=True, slots=True)
class RunLog:
    """
    Representation of a run log entry.
    """

    id: int
    caption: str
    posts: list[PostLog]


@dataclass(frozen=True, slots=True)
class Draft:
    """
    Representation of a draft for a future post.
    """

    name: str
    content: str
    post_form: PostForm
    targets: list[str]


@dataclass(frozen=True, slots=True)
class DraftSummary:
    """
    Summary of a draft entry to be used in UIs.
    """

    name: str
    post_form: PostForm
    updated_at: str
