#region Imports
import sys

from rich.console import Console

from src.storage.snapshot_db import (
    DEFAULT_DB_PATH,
    get_database_stats,
)
#endregion


#region Functions


def run(console: Console) -> None:
    """
    Delete all historical usage data from the database.
    Requires -f or --force flag to prevent accidental deletion.

    Args:
        console: Rich console for output

    Flags:
        -f or --force: Required flag to confirm deletion
    """
    force = "-f" in sys.argv or "--force" in sys.argv

    if not force:
        console.print("[red]WARNING: This will delete ALL historical usage data![/red]")
        console.print("[yellow]To confirm deletion, use: ccg remove usage --force[/yellow]")
        return

    db_path = DEFAULT_DB_PATH

    if not db_path.exists():
        console.print("[yellow]No historical database found.[/yellow]")
        return

    try:
        # Show stats before deletion
        db_stats = get_database_stats()
        if db_stats["total_records"] > 0:
            console.print("[cyan]Current database:[/cyan]")
            console.print(f"  Records: {db_stats['total_records']:,}")
            console.print(f"  Days: {db_stats['total_days']}")
            console.print(f"  Range: {db_stats['oldest_date']} to {db_stats['newest_date']}\n")

        # Delete the database file
        db_path.unlink()
        console.print("[green]✓ Successfully deleted historical usage database[/green]")
        console.print(f"[dim]Deleted: {db_path}[/dim]")

    except Exception as e:
        console.print(f"[red]Error deleting database: {e}[/red]")


#endregion
