from importlib.metadata import entry_points

from .platforms.base import Platform


def discover_platforms() -> dict[str, Platform]:
    platforms: dict[str, Platform] = {}

    eps = entry_points(group="pomeari.platforms")
    for ep in eps:
        cls = ep.load()
        platform = cls()
        if not isinstance(platform, Platform):
            continue
        platforms[ep.name] = platform

    return platforms
