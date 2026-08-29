from dataclasses import dataclass


class PomeariError(Exception):
    pass


class InvalidPostError(PomeariError):
    pass


class PlatformNotFoundError(PomeariError):
    def __init__(self, platform: str):
        self.platform = platform
        super().__init__(f"Platform '{platform}' is not available.")


class FavoritePlatformError(PomeariError):
    pass


@dataclass(frozen=True, slots=True)
class MissingConfigEntry:
    platform: str
    platform_title: str
    key: str
    description: str


class MissingConfigurationError(PomeariError):
    def __init__(self, entries: list[MissingConfigEntry]):
        self.entries = entries.copy()

        lines = []
        for entry in entries:
            lines.append(
                f"{entry.platform_title}: missing config entry "
                f"'{entry.key}' ({entry.description})"
            )

        super().__init__("\n".join(lines))


class DraftError(PomeariError):
    pass


class InvalidDraftNameError(DraftError):
    pass


class DraftNotFoundError(DraftError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Draft '{name}' does not exist.")
