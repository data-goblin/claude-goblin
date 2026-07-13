"""
Sync commands for Claude Goblin.

Provides subcommands for cross-device sync configuration:
- setup: Configure storage format and sync provider
- status: Show current sync configuration
- push: Push local records to every configured sink
- query: Run DAX against the Claude Usage semantic model
"""
#region Imports
import typer

from src.commands.sync import push, query, repair, setup, status

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
app.command(name="repair")(repair.repair_command)
app.command(name="query")(query.query_command)
#endregion
