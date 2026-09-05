import asyncio
import sys
from collections.abc import Coroutine, Iterable
from importlib.metadata import version
from typing import Any, TypeVar

import click

from .errors import MissingConfigurationError, PomeariError
from .service import PomeariService
from .types import PostForm, PublishRequest, PublishStatus, RunLog

T = TypeVar("T")


def _run(operation: Coroutine[Any, Any, T]) -> T:
    try:
        return asyncio.run(operation)
    except MissingConfigurationError as error:
        message = (
            f"{error}\n\nAdd the missing values with `pomeari config set KEY VALUE`."
        )
        raise click.ClickException(message) from error
    except PomeariError as error:
        raise click.ClickException(str(error)) from error


@click.group
@click.version_option(version=version("pomeari"))
def cli():
    pass


@cli.group
def config():
    """Manage configuration keys, including API secrets"""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def set_config(key: str, value: str):
    """Add or replace a configuration entry."""

    async def main():
        async with PomeariService() as service:
            await service.set_config(key, value)

    _run(main())
    click.echo(f"Set config key: {key}")


config.add_command(set_config, name="add")


@config.command("rm")
@click.argument("key")
def remove_config(key: str):
    """Remove a configuration entry."""

    async def main():
        async with PomeariService() as service:
            await service.remove_config(key)

    _run(main())
    click.echo(f"Removed config key: {key}")


@cli.group(invoke_without_command=True)
@click.pass_context
def platform(ctx):
    """Manage platforms"""
    if not ctx.invoked_subcommand:
        ctx.invoke(listcmd)


@platform.command("list")
def listcmd():
    """List available platforms."""

    async def main():
        async with PomeariService() as service:
            return await service.list_platforms()

    platforms = _run(main())
    if not platforms:
        click.echo("No platforms installed.")
        return

    lines = []
    for platform_info in platforms:
        title = platform_info.module.title or platform_info.name
        lines.append(f"{platform_info.name}\t{title}")
    click.echo_via_pager("\n".join(lines))


@platform.command("favorite")
@click.argument("platform_name", required=False)
def favorite(platform_name: str | None):
    """Get or set the favorite platform."""

    async def main():
        async with PomeariService() as service:
            if not platform_name:
                return await service.get_favorite_platform()

            await service.set_favorite_platform(platform_name)
            return platform_name

    selected = _run(main())
    if not platform_name:
        click.echo(f"Selected favorite platform: {selected}")
    else:
        click.echo(f"Favorite platform set to: {selected}")


@cli.group(invoke_without_command=True)
@click.pass_context
def post(ctx):
    """Post-related commands"""
    if not ctx.invoked_subcommand:
        ctx.invoke(short)


def _load_and_maybe_edit_content(
    *,
    file_input: str | None = None,
    message: str | None = None,
    edit: bool = False,
) -> str | None:
    content = ""

    if message:
        content = message
    elif file_input:
        with open(file_input, "r", encoding="utf-8") as file:
            content = file.read()
    elif not sys.stdin.isatty():
        content = sys.stdin.read()

    if edit or not content:
        edited = click.edit(content)
        if not edited:
            return None
        content = edited

    if not content.strip():
        return None

    return content


def _post_content(
    post_form: PostForm,
    content: str | None,
    targets: Iterable[str],
):
    if not content:
        click.echo("Aborted: empty post content.")
        return

    request_targets = targets or None
    request = PublishRequest(
        post_form=post_form,
        content=content,
        targets=request_targets,
    )

    async def main():
        async with PomeariService() as service:
            return await service.publish(request)

    click.echo("Posting to platforms...")
    published = _run(main())

    for result in published.platforms:
        if result.status == PublishStatus.SUCCESS and result.result:
            click.echo(f"{result.title} ({result.platform}): {result.result.url}")
        elif result.status == PublishStatus.SKIPPED:
            click.echo(f"{result.title} ({result.platform}): skipped ({result.error})")
        else:
            click.echo(
                f"{result.title} ({result.platform}): failed ({result.error})",
                err=True,
            )


@post.command
@click.argument("file_input", required=False, type=click.Path(exists=True))
@click.option("-m", "--message", help="Post content directly from the command line.")
@click.option("-e", "--edit", is_flag=True, help="Edit content before posting.")
@click.option(
    "-t",
    "--target",
    "targets",
    multiple=True,
    help="Post to this platform. Repeat to select multiple platforms.",
)
def short(file_input, message, edit, targets):
    """Post short-form content."""
    content = _load_and_maybe_edit_content(
        file_input=file_input,
        message=message,
        edit=edit,
    )
    _post_content(PostForm.SHORT, content, targets)


@post.command
@click.argument("file_input", required=False, type=click.Path(exists=True))
@click.option("-e", "--edit", is_flag=True, help="Edit content before posting.")
@click.option(
    "-t",
    "--target",
    "targets",
    multiple=True,
    help="Post to this platform. Repeat to select multiple platforms.",
)
def long(file_input, edit, targets):
    """Post long-form content."""
    content = _load_and_maybe_edit_content(
        file_input=file_input,
        edit=edit,
    )
    _post_content(PostForm.LONG, content, targets)


def _format_logs(history: Iterable[RunLog]) -> str:
    lines = []
    for run in history:
        lines.append(f'Run #{run.id} ("{run.caption}"):')

        for entry in run.posts:
            lines.append(f" ~> Platform: {entry.platform}")
            lines.append(f"    URL: {entry.url}")
            lines.append(f"    Created at: {entry.created_at}")
            if entry.metadata:
                lines.append(f"    Metadata: {entry.metadata}")
            lines.append("")

        lines.append("")

    return "\n".join(lines).rstrip()


@post.command
@click.option(
    "-n",
    "--max-count",
    default=100,
    type=click.IntRange(min=1),
    help="Max number of posting runs to show.",
)
def logs(max_count: int):
    """Show recent crossposting runs."""

    async def main():
        async with PomeariService() as service:
            return await service.get_history(max_count)

    history = _run(main())
    click.echo_via_pager(_format_logs(history))


@cli.group
def reset():
    """Reset parts of the local Pomeari database"""
    pass


@reset.command("config")
def reset_config():
    """Reset all Pomeari configuration entries."""
    click.confirm(
        "Are you sure you want to lose all your configuration entries forever?",
        abort=True,
    )

    async def main():
        async with PomeariService() as service:
            await service.clear_config()

    _run(main())
    click.echo("Reset all configuration entries.")


@reset.command("logs")
def reset_logs():
    """Reset all Pomeari run and post log entries."""
    click.confirm(
        "Are you sure you want to lose all your run and post logs forever?",
        abort=True,
    )

    async def main():
        async with PomeariService() as service:
            await service.clear_history()

    _run(main())
    click.echo("Reset all run and post log entries.")


@reset.command("all")
def reset_all():
    """Reset the entire Pomeari database."""
    click.confirm(
        "You're about to delete the entirety of your Pomeari database. "
        "This includes all configuration entries, posting history, and your "
        "favorite platform choice. Are you sure?",
        abort=True,
    )

    async def main():
        async with PomeariService() as service:
            await service.reset_database()

    _run(main())
    click.echo("Reset the entire Pomeari database.")


if __name__ == "__main__":
    cli()
