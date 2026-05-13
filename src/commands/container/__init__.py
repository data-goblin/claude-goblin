"""
Container commands for Claude Goblin.

Provides subcommands for container-related operations:
- sync: Sync data between container and host
- status: Show container sync status
"""
import typer

from src.commands.container import sync

# Create container sub-app
app = typer.Typer(
    name="container",
    help="Container data sync and management",
    no_args_is_help=True,
)

# Register subcommands
app.command(name="sync")(sync.sync_command)
app.command(name="status")(sync.status_command)
