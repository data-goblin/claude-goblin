"""
Sync commands for Claude Goblin.

Provides subcommands for cross-device sync configuration:
- setup: Configure storage format and sync provider
- status: Show current sync configuration
- add-device: Add a remote device (Syncthing only)
"""
#region Imports
import typer

from src.commands.sync import setup, status, push
#endregion


#region App Setup
app = typer.Typer(
    name="sync",
    help="Cross-device sync configuration",
    no_args_is_help=True,
)
#endregion


#region Command Registration
app.command(name="setup")(setup.setup_sync_command)
app.command(name="status")(status.sync_status_command)
app.command(name="push")(push.push_command)
#endregion
