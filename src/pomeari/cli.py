import asyncio
from typing import Any

import click

from pomeari.db import get_run_logs

from .types import PostForm


def _read_version():
    import tomllib

    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    return pyproject["project"]["version"]


@click.group
@click.version_option(version=_read_version())
def cli():
    pass


@cli.group
def config():
    """Manage configuration keys, including API secrets"""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def set(key, value):
    """Add/replace a configuration entry."""
    from .db import set_conf

    asyncio.run(set_conf(key, value))
    click.echo(f"Set config key {key} to {value}")


config.add_command(set, name="add")


@config.command("rm")
@click.argument("key")
def rm(key):
    """Remove (clear) a configuration entry."""
    from .db import rm_conf

    asyncio.run(rm_conf(key))
    click.echo(f"Removed config key: {key}")


@cli.group(invoke_without_command=True)
@click.pass_context
def platform(ctx):
    """Manage platforms"""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list)


@platform.command("list")
def listcmd():
    """List available platforms"""
    from .ep import discover_platforms

    platforms = discover_platforms()
    if not platforms:
        click.echo("No platforms installed.")
        return

    lines = []
    for name, platform in platforms.items():
        title = platform.info.title or name
        lines.append(f"{name}\t{title}")

    click.echo_via_pager("\n".join(lines))


@platform.command("favorite")
@click.argument("platform", required=False)
def favorite(platform: str | None):
    """Get or set the favorite platform"""
    from .db import get_favorite_platform, init_db, set_favorite_platform
    from .ep import discover_platforms

    async def main():
        await init_db()
        if platform is None:
            fav = await get_favorite_platform()
            click.echo(f"Selected favorite platform: {fav}")
            return

        platforms = discover_platforms()
        if platform not in platforms:
            raise click.ClickException(
                f"Platform '{platform}' not found. "
                f"Available: {', '.join(platforms.keys())}"
            )

        await set_favorite_platform(platform)
        click.echo(f"Favorite platform set to: {platform}")

    asyncio.run(main())


@cli.group(invoke_without_command=True)
@click.pass_context
def post(ctx):
    """Post-related commands"""
    if ctx.invoked_subcommand is None:
        ctx.invoke(short)


def _load_and_maybe_edit_content(
    *,
    file_input: str | None = None,
    message: str | None = None,
    stdin: bool = False,
    edit: bool = False,
) -> str | None:
    content = ""

    if message is not None:
        content = message
    elif stdin:
        if click.get_text_stream("stdin").isatty():
            return None
        content = click.get_text_stream("stdin").read()
    elif file_input:
        with open(file_input, "r", encoding="utf-8") as f:
            content = f.read()

    if edit or not content:
        edited = click.edit(content)
        if edited is None:
            return None
        content = edited

    if not content.strip():
        return None

    return content


def _post_content(post_form: PostForm, content: str | None):
    if content is None:
        click.echo("Aborted: empty post content.")
        return

    from .db import init_db, load_config
    from .posts import post_to_platforms

    async def main():
        await init_db()
        config = await load_config()
        click.echo("Posting to platforms...")
        results = await post_to_platforms(post_form, content, config)
        for mod, res in results.items():
            if isinstance(res, Exception) or res is None:
                # click.echo(f"{mod}: {res}")
                continue
            click.echo(f"{mod}: {res.url}")

    asyncio.run(main())


@post.command
@click.argument("file_input", required=False, type=click.Path(exists=True))
@click.option("-m", "--message", help="Post content directly from the command line.")
@click.option("--stdin", is_flag=True, help="Read post content from stdin.")
@click.option("-e", "--edit", is_flag=True, help="Edit content before posting.")
def short(file_input, message, stdin, edit):
    """Post short-form content."""
    content = _load_and_maybe_edit_content(
        file_input=file_input,
        message=message,
        stdin=stdin,
        edit=edit,
    )
    _post_content(PostForm.SHORT, content)


@post.command
@click.argument("file_input", required=False, type=click.Path(exists=True))
@click.option("--stdin", is_flag=True, help="Read post content from stdin.")
@click.option("-e", "--edit", is_flag=True, help="Edit content before posting.")
def long(file_input, stdin, edit):
    """Post short-form content."""
    content = _load_and_maybe_edit_content(
        file_input=file_input,
        stdin=stdin,
        edit=edit,
    )
    _post_content(PostForm.LONG, content)


@post.command
@click.option(
    "-n", "--max-count", default=100, help="Max number of log entries to show."
)
def logs(max_count: int):
    """Show last 100 (or specified) logged crossposts."""
    from collections import defaultdict

    from .db import get_post_logs, init_db

    def _format_logs(
        entries: list[dict[str, Any]], run_captions: dict[int, Any]
    ) -> str:
        runs: dict[int, list[dict]] = defaultdict(list)
        for entry in entries:
            runs[entry["id"]].append(entry)

        lines: list[str] = []

        for run_id in sorted(runs, reverse=True):
            lines.append(f'Run #{run_id} ("{run_captions.get(run_id, "???")}"):')

            for entry in runs[run_id]:
                lines.append(f" ~> Platform: {entry['platform']}")
                lines.append(f"    URL: {entry['url']}")
                lines.append(f"    Created at: {entry['created_at']}")
                if entry["metadata"]:
                    lines.append(f"    Metadata: {entry['metadata']}")
                lines.append("")

            lines.append("")

        return "\n".join(lines).rstrip()

    async def main():
        await init_db()
        entries = await get_post_logs(max_count)
        run_log = await get_run_logs(max_count)  # an acceptable overestimation
        click.echo_via_pager(_format_logs(entries, run_log))

    asyncio.run(main())


@cli.group
def reset():
    """Reset (parts of) the local Pomeari database"""
    pass


@reset.command("config")
def reset_config():
    """Reset all Pomeari configuration entries."""
    from .db import clear_table

    click.confirm(
        "Are you sure you want to LOSE all your configuration entries FOREVER?",
        abort=True,
    )

    asyncio.run(clear_table("config"))
    click.echo(f"Reset all configuration entries.")


@reset.command("logs")
def reset_logs():
    """Reset all Pomeari run/post log entries."""
    from .db import clear_table

    click.confirm(
        "Are you sure you want to LOSE all your run and post logs FOREVER?",
        abort=True,
    )

    async def main():
        await clear_table("run_log")
        await clear_table("post_log")
        await clear_table("run_counter")
        click.echo(f"Reset all run/post log entries.")

    asyncio.run(main())


@reset.command("all")
def reset_all():
    """Reset the entire Pomeari database."""
    from pathlib import Path
    from .db import DB_PATH, init_db

    click.confirm(
        "You're about to delete the entirety of your Pomeari database. "
        "This includes all your configuration entries (API keys, settings...), "
        "all your run and post logs, and your favorite platform choice.\n"
        "Are you sure you're okay with that?",
        abort=True,
    )

    DB_PATH.unlink(missing_ok=True)
    asyncio.run(init_db())
    click.echo(f"Reset the entire Pomeari database.")


if __name__ == "__main__":
    cli()
