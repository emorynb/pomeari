from dataclasses import dataclass
from collections.abc import Iterable


class PomeariError(Exception):
    """The common base class for expected, user-facing Pomeari failures."""

    pass


class InvalidPostError(PomeariError):
    """Raised when a ``PublishRequest`` cannot be processed.

    May be caused by any of the following:

    - empty content;
    - an empty explicit target list;
    - malformed long-form content;
    - absence of compatible platforms.
    """

    pass


class PlatformNotFoundError(PomeariError):
    """Raised when a requested or selected ``Platform`` name is not among the
    available adapters.

    The constructor retains the missing name in ``platform`` and creates the
    exception message automatically.
    """

    def __init__(self, platform: str):
        self.platform = platform
        super().__init__(f"Platform '{platform}' is not available.")


class FavoritePlatformError(PomeariError):
    """Raised when a long-form ``PublishRequest`` cannot use the configured
    favorite ``Platform``.

    May be caused by any of the following:

    - missing adapter;
    - favorite omitted from explicit targets;
    - favorite lacks long-form support.
    """

    pass


@dataclass(frozen=True, slots=True)
class MissingConfigEntry:
    """Describes an absent configuration value.

    - ``platform``: registered platform name.
    - ``platform_title``: human-readable title.
    - ``key``: missing configuration key.
    - ``description``: describes what the key is needed for in the first place.
    """

    platform: str
    platform_title: str
    key: str
    description: str


class MissingConfigurationError(PomeariError):
    """Raised before publishing when one or more selected ``Platform``s lack
    necessary configuration entries.

    The collected ``MissingConfigEntry`` objects are stored in its ``entries``
    attribute and are formatted into a multiline exception message
    automatically.
    """

    def __init__(self, entries: Iterable[MissingConfigEntry]):
        self.entries = list(entries)

        lines = []
        for entry in self.entries:
            lines.append(
                f"{entry.platform_title}: missing config entry "
                f"'{entry.key}' ({entry.description})"
            )

        super().__init__("\n".join(lines))


class DraftError(PomeariError):
    """The common base class for draft storage failures."""

    pass


class InvalidDraftNameError(DraftError):
    """Raised when a draft name is empty or contains path components."""

    pass


class DraftNotFoundError(DraftError):
    """Raised when loading or deleting a draft whose file does not exist.

    The constructor retains the requested name in ``name`` and creates the
    exception message automatically.
    """

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Draft '{name}' does not exist.")
