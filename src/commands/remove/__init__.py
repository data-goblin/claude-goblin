"""
Remove commands for Claude Goblin.

Provides subcommands for removing various integrations:
- hooks: Remove Claude Code hooks
- usage: Remove historical usage database
"""
import typer

from src.commands.remove import hooks, usage


# Create remove sub-app
app = typer.Typer(
    name="remove",
    help="Remove integrations and configurations",
    no_args_is_help=True,
)


# Register subcommands
app.command(name="hooks")(hooks.remove_hooks_command)
app.command(name="usage")(usage.remove_usage_command)
