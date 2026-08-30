import asyncio
import logging
from collections.abc import Awaitable, Iterable, Mapping

import frontmatter

from .db import Database
from .errors import (
    FavoritePlatformError,
    InvalidPostError,
    MissingConfigEntry,
    MissingConfigurationError,
    PlatformNotFoundError,
)
from .platforms.base import Platform
from .types import (
    PlatformPublishResult,
    PostForm,
    PublishRequest,
    PublishResult,
    PublishStatus,
    XpostResult,
)


def _platform_title(name: str, platform: Platform) -> str:
    return platform.info.title or name


def _selected_platforms(
    request: PublishRequest,
    platforms: Mapping[str, Platform],
) -> Iterable[str]:
    if request.targets is None:
        if request.post_form == PostForm.SHORT:
            return [
                name
                for name, platform in platforms.items()
                if platform.supports_post_short()
            ]
        return list(platforms)

    selected = []
    for name in request.targets:
        if name not in platforms:
            raise PlatformNotFoundError(name)
        if name not in selected:
            selected.append(name)

    if not selected:
        raise InvalidPostError("Select at least one platform before publishing.")

    return selected


def _validate_favorite(
    request: PublishRequest,
    platforms: Mapping[str, Platform],
    selected: Iterable[str],
    favorite_name: str,
):
    if request.post_form != PostForm.LONG:
        return

    if favorite_name not in platforms:
        raise FavoritePlatformError(
            f"Favorite platform '{favorite_name}' is not available. "
            "It may have been uninstalled."
        )

    if favorite_name not in selected:
        raise FavoritePlatformError(
            f"Favorite platform '{favorite_name}' must be selected for a long post."
        )

    favorite = platforms[favorite_name]
    if not favorite.supports_post_long():
        title = _platform_title(favorite_name, favorite)
        raise FavoritePlatformError(
            f"Favorite platform '{title}' does not support long-form posts."
        )


def _platform_configs(
    selected: Iterable[str],
    platforms: Mapping[str, Platform],
    config: Mapping[str, str],
) -> Mapping[str, Mapping[str, str]]:
    missing = []
    stripped_configs = {}

    for name in selected:
        platform = platforms[name]
        title = _platform_title(name, platform)
        stripped = {}

        for entry in platform.info.config_keys:
            has_value = entry.key in config
            needs_value = entry.required or entry.default is None
            if not has_value and needs_value:
                missing.append(
                    MissingConfigEntry(
                        platform=name,
                        platform_title=title,
                        key=entry.key,
                        description=entry.description,
                    )
                )
                continue
            value = config.get(entry.key, entry.default)
            if value is None:
                continue
            stripped[entry.key] = value

        stripped_configs[name] = stripped

    if missing:
        raise MissingConfigurationError(missing)

    return stripped_configs


def _caption(request: PublishRequest) -> tuple[str, str | frontmatter.Post]:
    if not request.content.strip():
        raise InvalidPostError("Post content cannot be empty.")

    if request.post_form == PostForm.SHORT:
        caption = request.content[:20].rstrip()
        return caption, request.content

    try:
        post = frontmatter.loads(request.content)
    except Exception as error:
        raise InvalidPostError(
            f"Unable to parse the long-form post: {error}"
        ) from error

    title = post.metadata.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip(), post

    return request.content[:20].rstrip(), post


async def _run_handler(
    run_id: int,
    name: str,
    platform: Platform,
    handler: Awaitable[XpostResult],
    database: Database,
) -> PlatformPublishResult:
    title = _platform_title(name, platform)

    try:
        result = await handler
    except NotImplementedError:
        return PlatformPublishResult(
            platform=name,
            title=title,
            status=PublishStatus.SKIPPED,
            error="This platform does not support the requested post form.",
        )
    except Exception as error:
        logging.warning("Failed to post for %s: %s", title, error)
        return PlatformPublishResult(
            platform=name,
            title=title,
            status=PublishStatus.FAILED,
            error=str(error),
        )

    try:
        await database.log_post(run_id, name, result)
    except Exception as error:
        logging.warning("Failed to log post for %s: %s", title, error)

    return PlatformPublishResult(
        platform=name,
        title=title,
        status=PublishStatus.SUCCESS,
        result=result,
    )


async def publish_to_platforms(
    request: PublishRequest,
    platforms: Mapping[str, Platform],
    favorite_name: str,
    config: Mapping[str, str],
    database: Database,
) -> PublishResult:
    selected = _selected_platforms(request, platforms)
    if not selected:
        raise InvalidPostError("No compatible platforms are available.")

    _validate_favorite(request, platforms, selected, favorite_name)
    config_targets = selected
    if request.post_form == PostForm.SHORT:
        config_targets = [
            name for name in selected if platforms[name].supports_post_short()
        ]

    platform_configs = _platform_configs(config_targets, platforms, config)
    caption, post = _caption(request)

    run_id = await database.next_run_id()
    try:
        await database.log_run(run_id, caption)
    except Exception as error:
        logging.warning("Failed to log run #%d: %s", run_id, error)

    if request.post_form == PostForm.SHORT:
        handlers = []
        skipped_results = []
        for name in selected:
            platform = platforms[name]
            if not platform.supports_post_short():
                skipped_results.append(
                    PlatformPublishResult(
                        platform=name,
                        title=_platform_title(name, platform),
                        status=PublishStatus.SKIPPED,
                        error="This platform does not support short-form posts.",
                    )
                )
                continue
            handlers.append(
                _run_handler(
                    run_id,
                    name,
                    platform,
                    platform.post_short(post, platform_configs[name]),  # type: ignore[arg-type]
                    database,
                )
            )

        published_results = await asyncio.gather(*handlers)
        unordered_results = [*published_results, *skipped_results]
        results_by_platform = {result.platform: result for result in unordered_results}
        ordered_results = [results_by_platform[name] for name in selected]
        return PublishResult(run_id, caption, ordered_results)

    favorite = platforms[favorite_name]
    favorite_result = await _run_handler(
        run_id,
        favorite_name,
        favorite,
        favorite.post_long(post, platform_configs[favorite_name]),  # type: ignore[arg-type]
        database,
    )

    remaining_handlers = []
    skipped_results = []

    for name in selected:
        if name == favorite_name:
            continue

        platform = platforms[name]
        if platform.supports_post_long():
            handler = platform.post_long(post, platform_configs[name])  # type: ignore[arg-type]
        elif (
            favorite_result.status == PublishStatus.SUCCESS
            and favorite_result.result is not None
        ):
            relay_content = f"{caption}\n\n{favorite_result.result.url}"
            handler = platform.post_short(relay_content, platform_configs[name])
        else:
            skipped_results.append(
                PlatformPublishResult(
                    platform=name,
                    title=_platform_title(name, platform),
                    status=PublishStatus.SKIPPED,
                    error="The primary long-form post failed, so its relay was skipped.",
                )
            )
            continue

        remaining_handlers.append(
            _run_handler(run_id, name, platform, handler, database)
        )

    remaining_results = await asyncio.gather(*remaining_handlers)
    unordered_results = [favorite_result, *remaining_results, *skipped_results]
    results_by_platform = {result.platform: result for result in unordered_results}
    ordered_results = [results_by_platform[name] for name in selected]

    return PublishResult(run_id, caption, ordered_results)
