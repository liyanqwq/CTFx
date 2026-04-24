"""Click entry point — registers all command groups and top-level aliases."""

import sys
import click

from ctfx import __version__
from ctfx.exceptions import CTFxError
from ctfx.commands.competition import comp_group, cmd_use, cmd_init
from ctfx.commands.challenge import chal_group, cmd_add
from ctfx.commands.terminal import cmd_cli, cmd_wsl, cmd_explorer, cmd_code, cmd_py
from ctfx.commands.platform import cmd_fetch, cmd_submit, cmd_import
from ctfx.commands.serve import cmd_serve
from ctfx.commands.ai import cmd_ai, cmd_mcp
from ctfx.commands.awd import awd_group
from ctfx.commands.api import api_group
from ctfx.commands.setup import cmd_setup
from ctfx.commands.token import token_group
from ctfx.commands.webui import cmd_webui
from ctfx.commands.interactive import cmd_interactive
from ctfx.commands.config import config_group
from ctfx.commands.toolkit import toolkit_group


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="ctfx")
@click.pass_context
def main(ctx: click.Context) -> None:
    """ctfx — CTF workspace manager and assistant.

    Local-first CTF workspace manager. Run 'ctfx setup' on first use.
    Docs: https://github.com/liyanqwq/CTFx
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _main() -> None:
    """Wrapper that catches CTFxError for clean user-facing output."""
    try:
        main(standalone_mode=True)
    except CTFxError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(1)


# Command groups
main.add_command(comp_group, name="comp")
main.add_command(chal_group, name="chal")
main.add_command(awd_group, name="awd")
main.add_command(api_group, name="api")
main.add_command(token_group, name="token")
main.add_command(config_group, name="config")
main.add_command(toolkit_group, name="toolkit")

# Direct commands
main.add_command(cmd_cli, name="cli")
main.add_command(cmd_wsl, name="wsl")
main.add_command(cmd_explorer, name="explorer")
main.add_command(cmd_explorer, name="e")
main.add_command(cmd_code, name="code")
main.add_command(cmd_py, name="py")
main.add_command(cmd_fetch, name="fetch")
main.add_command(cmd_submit, name="submit")
main.add_command(cmd_import, name="import")
main.add_command(cmd_serve, name="serve")
main.add_command(cmd_ai, name="ai")
main.add_command(cmd_mcp, name="mcp")
main.add_command(cmd_setup, name="setup")
main.add_command(cmd_webui, name="webui")
main.add_command(cmd_webui, name="web")
main.add_command(cmd_webui, name="ui")
main.add_command(cmd_interactive, name="interactive")
main.add_command(cmd_interactive, name="i")

# Top-level aliases
main.add_command(cmd_use, name="use")
main.add_command(cmd_init, name="init")
main.add_command(cmd_add, name="add")


@main.command("help")
@click.pass_context
def cmd_help(ctx: click.Context) -> None:
    """Show this help message."""
    click.echo(ctx.find_root().get_help())
