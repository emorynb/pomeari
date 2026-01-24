import asyncio
from typing import Any

import click

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


@config.command("add")
@click.argument("key")
@click.argument("value")
def add(key, value):
    """Add/replace a configuration entry."""
    from .db import add_conf

    asyncio.run(add_conf(key, value))
    click.echo(f"Added config key: {key}")


@config.command("rm")
@click.argument("key")
def rm(key):
    """Remove (clear) a configuration entry."""
    from .db import rm_conf

    asyncio.run(rm_conf(key))
    click.echo(f"Removed config key: {key}")


@cli.group(invoke_without_command=True)
@click.pass_context
def platforms(ctx):
    """Manage platforms"""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list)


@platforms.command("list")
def list():
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


@platforms.command("favorite")
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


def _format_logs(entry: dict[str, Any]) -> str:
    arr = []
    for v in entry.values():
        arr.append(str(v))
    return " ".join(arr)


@post.command
@click.option(
    "-n", "--max-count", default=10, help="Max number of log entries to show."
)
def logs(max_count: int):
    """Show last 100 (or specified) logged crossposts."""
    from .db import get_post_logs, init_db

    async def main():
        await init_db()
        entries = await get_post_logs(max_count)
        click.echo_via_pager("\n".join(_format_logs(e) for e in entries))

    asyncio.run(main())


if __name__ == "__main__":
    cli()
