from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import NamedTuple


class PostForm(StrEnum):
    """
    Dictates what a post is in terms of its length-form substance.
    """

    SHORT = auto()  # "i just shat my pants get ratio'd"
    LONG = auto()  # Why I Am The Golden God (11-page guide to superior life forms)"


class PlatformConfig(NamedTuple):
    """
    Representation of a config entry required by a Platform-implementing module.

    Typing does not exist here because otherwise it would needlessly complicate
    storing the entries. It's on the modules to communicate types to the user
    directly in the description and to parse them into whatever representation
    they need.
    """

    key: str
    description: str
    required: bool = False
    default: str | None = None


@dataclass(slots=True)
class ModuleInfo:
    """
    Base information about a Platform implementation module.
    """

    title: str | None = None
    config_keys: list[PlatformConfig] = field(default_factory=list)


@dataclass
class XpostResult:
    """
    Result data structure for returning in Platform post handlers, containing
    information about what and at which moment has just been crossposted, as
    well as if any new config entries need to be loaded.

    'metadata' is fully optional and its format is not enforced by Pomeari. It
    is however recommended that you document the format you use and have it be
    deterministic for potential future parsing if you are to put anything there.
    """

    url: str
    created_at: str | None = None
    config_update: dict = field(default_factory=dict)
    metadata: str | None = None


class PublishStatus(StrEnum):
    """
    Indicates the result of a post publishing attempt, per-run.
    """
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass(frozen=True, slots=True)
class PublishRequest:
    """
    Representation of a request to publish a post to select or all platform(s).
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
    """
    Information about a Platform implementation (nests ModuleInfo).
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
