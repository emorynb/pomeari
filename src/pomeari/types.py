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
    (Optional) information about a Platform implementation.
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
