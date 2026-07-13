#region Imports
import os
import shutil
from datetime import datetime

from rich.console import Console

from src.storage import api

#endregion


#region Functions


def run(console: Console) -> None:
    """
    Restore database from backup file.

    Restores the usage history database from a backup file (.db.bak).
    Creates a safety backup of the current database before restoring.

    Args:
        console: Rich console for output
    """
    db_path = api.current_db_path()
    backup_path = db_path.parent / f"{db_path.name}.bak"

    if not backup_path.exists():
        console.print("[yellow]No backup file found.[/yellow]")
        console.print(f"[dim]Expected location: {backup_path}[/dim]")
        return

    console.print("[bold cyan]Restore Database from Backup[/bold cyan]\n")
    console.print(f"[yellow]Backup file: {backup_path}[/yellow]")
    console.print(f"[yellow]This will replace: {db_path}[/yellow]")

    # Show backup file info
    backup_size = os.path.getsize(backup_path)
    backup_time = os.path.getmtime(backup_path)
    backup_date = datetime.fromtimestamp(backup_time).strftime("%Y-%m-%d %H:%M:%S")

    console.print(f"[dim]Backup size: {backup_size:,} bytes[/dim]")
    console.print(f"[dim]Backup date: {backup_date}[/dim]")
    console.print("")

    if db_path.exists():
        console.print("[bold red]⚠️  WARNING: This will overwrite your current database![/bold red]")
        console.print("[yellow]Consider backing up your current database first.[/yellow]")
        console.print("")

    console.print("[cyan]Continue with restore? (yes/no):[/cyan] ", end="")

    try:
        confirm = input().strip().lower()
        if confirm not in ["yes", "y"]:
            console.print("[yellow]Restore cancelled[/yellow]")
            return
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Restore cancelled[/yellow]")
        return

    try:
        # Create a backup of current DB if it exists
        if db_path.exists():
            current_backup = db_path.parent / f"{db_path.name}.before_restore"
            shutil.copy2(db_path, current_backup)
            console.print(f"[dim]Current database backed up to: {current_backup}[/dim]")

        # Restore from backup
        shutil.copy2(backup_path, db_path)
        console.print("[green]✓ Database restored from backup[/green]")
        console.print(f"[dim]Restored: {db_path}[/dim]")

        # Show restored stats
        db_stats = api.get_database_stats()
        if db_stats["total_records"] > 0:
            console.print("")
            console.print("[cyan]Restored database contains:[/cyan]")
            console.print(f"  Records: {db_stats['total_records']:,}")
            console.print(f"  Days: {db_stats['total_days']}")
            console.print(f"  Range: {db_stats['oldest_date']} to {db_stats['newest_date']}")

    except Exception as e:
        console.print(f"[red]Error restoring backup: {e}[/red]")


#endregion
