"""
Restore usage command.

Restores usage database from backup file.
"""
import typer
from rich.console import Console

from src.commands import restore_backup as _restore_backup_module


def restore_usage_command() -> None:
    """
    Restore usage database from backup file.

    Restores the usage history database from a backup file (.db.bak).
    Creates a safety backup of the current database before restoring.

    Expected backup location: ~/.claude/usage/usage_history.db.bak

    Examples:
        ccg restore usage    Restore usage database from backup
    """
    console = Console()
    _restore_backup_module.run(console)
