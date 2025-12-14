"""
Remove usage command.

Removes historical usage database (with automatic backup).
"""
import shutil
from datetime import datetime

import typer
from rich.console import Console

from src.storage.snapshot_db import (
    DEFAULT_DB_PATH,
    get_database_stats,
)


def remove_usage_command(
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Force deletion without confirmation"
    ),
) -> None:
    """
    Remove historical usage database.

    WARNING: This will permanently delete all historical usage data!
    A backup is automatically created before deletion.

    Requires --force flag to prevent accidental deletion.

    Examples:
        ccg remove usage --force    Remove usage database (creates backup first)
    """
    console = Console()

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

        # Create backup before deletion
        backup_path = db_path.parent / f"usage_history.db.bak"
        timestamp_backup = db_path.parent / f"usage_history.{datetime.now().strftime('%Y%m%d_%H%M%S')}.db.bak"

        # Always keep the .bak file for restore command
        shutil.copy2(db_path, backup_path)
        console.print(f"[green]Backup created: {backup_path}[/green]")

        # Also keep a timestamped backup for safety
        shutil.copy2(db_path, timestamp_backup)
        console.print(f"[dim]Timestamped backup: {timestamp_backup}[/dim]")

        # Delete the database file
        db_path.unlink()
        console.print(f"\n[green]Successfully removed historical usage database[/green]")
        console.print(f"[dim]Deleted: {db_path}[/dim]")
        console.print(f"\n[dim]To restore: ccg restore usage[/dim]")

    except Exception as e:
        console.print(f"[red]Error removing database: {e}[/red]")
