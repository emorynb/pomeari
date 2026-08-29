import asyncio
import logging
from typing import Any

import click
import frontmatter

from .db import get_favorite_platform, inc_and_get_run_id, log_post, log_run
from .ep import discover_platforms
from .types import ModuleInfo, PostForm, XpostResult


async def _wrap(run_id: int, display_name: str, coro: Any):
    try:
        result = await coro
    except NotImplementedError as e:
        raise e  # just silently pass
    except Exception as e:
        logging.warning("Failed to post for %s: %s", display_name, e)
        raise e

    try:
        await log_post(run_id, display_name, result)
    except Exception as e:
        logging.warning("Failed to log post for %s: %s", display_name, e)
    return result


async def _raise_ni(*_, **__):
    raise NotImplementedError


async def post_to_platforms(
    post_form: PostForm, content: str, config: dict
) -> dict[str, XpostResult | Exception]:
    platforms = discover_platforms()
    favorite_name = await get_favorite_platform()

    if favorite_name not in platforms:
        raise click.ClickException(
            f"Favorite platform '{favorite_name}' is not available. "
            "It may have been uninstalled."
        )

    run_id = await inc_and_get_run_id()

    if post_form == PostForm.SHORT:
        post = content
        run_caption = content[:20].rstrip()  # not the best solution but meh
    else:
        post = frontmatter.loads(content)
        run_caption: str = (
            post["title"] if "title" in post else content[:20].rstrip()
        )  # pyright: ignore

    try:
        await log_run(run_id, run_caption)
    except Exception as e:
        logging.warning("Failed to log run #%d: %s", run_id, e)

    # validate configs for all platforms upfront
    stripped_configs: dict[str, dict[str, str]] = {}
    for name, platform in platforms.items():
        info = platform.info
        missing = [
            c
            for c in info.config_keys
            if (c.required or c.default is None) and c.key not in config
        ]
        if missing:
            excstrs = [
                f"{info.title}: missing config entry '{c.key}' ({c.description})"
                for c in missing
            ]
            raise click.ClickException(
                "\n".join(excstrs + ["\nAdd them via `pomeari config add key value`!"])
            )
        stripped_configs[name] = {
            k.key: config.get(k.key, k.default) for k in info.config_keys
        }

    if post_form == PostForm.LONG:
        if not platforms[favorite_name].supports_post_long():
            raise click.ClickException(
                f"Favorite platform '{platforms[favorite_name].info.title}' "
                "does not support long-form posts. "
                "Set a long-form-capable platform as your favorite."
            )

    # run favorite platform first
    fav_platform = platforms[favorite_name]
    fav_display = f"{fav_platform.info.title} ({favorite_name})"

    if post_form == PostForm.LONG:
        fav_handler = fav_platform.post_long
    else:
        fav_handler = fav_platform.post_short

    fav_args = (post, stripped_configs[favorite_name])
    fav_result: XpostResult | Exception | None = None
    try:
        fav_result = await _wrap(run_id, fav_display, fav_handler(*fav_args))
    except Exception as e:
        fav_result = e

    # build coros for remaining platforms
    coros: dict[str, Any] = {}
    for name, platform in platforms.items():
        if name == favorite_name:
            continue

        display_name = f"{platform.info.title} ({name})"
        stripped = stripped_configs[name]

        if post_form == PostForm.LONG and not platform.supports_post_long():
            if isinstance(fav_result, XpostResult):
                relay_content = f"{run_caption}\n\n{fav_result.url}"
                coros[display_name] = _wrap(
                    run_id,
                    display_name,
                    platform.post_short(relay_content, stripped),
                )
            else:
                logging.warning(
                    "Relay skipped for %s — favorite platform returned: %s",
                    display_name,
                    fav_result,
                )
                coros[display_name] = _wrap(run_id, display_name, _raise_ni())
        else:
            if post_form == PostForm.LONG:
                handler = platform.post_long
                handler_args = (post, stripped)
            else:
                handler = platform.post_short
                handler_args = (post, stripped)

            coros[display_name] = _wrap(run_id, display_name, handler(*handler_args))

    results = await asyncio.gather(*coros.values(), return_exceptions=True)
    combined: dict[str, XpostResult | Exception] = dict(
        zip(coros.keys(), results)
    )  # pyright: ignore
    if fav_result is not None:
        combined = {fav_display: fav_result, **combined}

    return combined
