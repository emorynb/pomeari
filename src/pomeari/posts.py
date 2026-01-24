import asyncio
import logging
from typing import Any

import click
import frontmatter

from .db import get_favorite_platform, inc_and_get_run_id, log_post
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


async def post_to_platforms(
    post_form: PostForm, content: str, config: dict
) -> dict[str, XpostResult | Exception]:
    platforms = discover_platforms()
    coros: dict[str, Any] = {}
    fav_result: XpostResult | Exception | None = None

    favorite_name = await get_favorite_platform()
    run_id = await inc_and_get_run_id()

    for name, platform in platforms.items():
        info: ModuleInfo = platform.info
        config_keys = info.config_keys

        missing = [
            c
            for c in config_keys
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

        stripped_config = {k.key: config.get(k.key, k.default) for k in config_keys}

        handler_attr = f"post_{post_form}"
        handler = getattr(platform, handler_attr, None)
        if handler is None:

            async def raise_ni(*_, **__):
                raise NotImplementedError

            handler = raise_ni

        display_name = f"{info.title} ({name})"

        # favorite runs *outside* gather
        if name == favorite_name:
            try:
                fav_coro = handler(
                    content
                    if post_form == PostForm.SHORT
                    else frontmatter.loads(content),
                    stripped_config,
                )
                fav_result = await _wrap(run_id, display_name, fav_coro)
            except Exception as e:
                fav_result = e
        else:
            coros[display_name] = _wrap(
                run_id,
                display_name,
                handler(
                    content
                    if post_form == PostForm.SHORT
                    else frontmatter.loads(content),
                    stripped_config,
                ),
            )

    results = await asyncio.gather(*coros.values(), return_exceptions=True)

    # build final mapping and insert favorite at front
    combined: dict[str, XpostResult | Exception] = dict(zip(coros.keys(), results))  # pyright: ignore
    if fav_result is not None:
        combined = {
            f"{platforms[favorite_name].info.title} ({favorite_name})": fav_result,
            **combined,
        }

    return combined
