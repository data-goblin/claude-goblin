"""
Update commands for Claude Goblin.

Provides subcommands for updating data:
- usage: Update historical usage database
"""
import typer

from src.commands.update import usage


# Create update sub-app
app = typer.Typer(
    name="update",
    help="Update data and databases",
    no_args_is_help=True,
)


# Register subcommands
app.command(name="usage")(usage.update_usage_command)
