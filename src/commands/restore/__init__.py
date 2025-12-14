"""
Restore commands for Claude Goblin.

Provides subcommands for restoring from backups:
- usage: Restore usage database from backup
"""
import typer

from src.commands.restore import usage


# Create restore sub-app
app = typer.Typer(
    name="restore",
    help="Restore from backups",
    no_args_is_help=True,
)


# Register subcommands
app.command(name="usage")(usage.restore_usage_command)
