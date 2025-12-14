"""
Setup commands for Claude Goblin.

Provides subcommands for setting up various integrations:
- hooks: Claude Code hooks for automation
- container: Devcontainer for safe execution
"""
import typer

from src.commands.setup import hooks, container


# Create setup sub-app
app = typer.Typer(
    name="setup",
    help="Setup integrations and configurations",
    no_args_is_help=True,
)


# Register subcommands
app.command(name="hooks")(hooks.setup_hooks_command)
app.command(name="container")(container.setup_container_command)
