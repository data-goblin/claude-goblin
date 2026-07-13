"""
Sync repair command for Claude Goblin.

Rebuilds the quack remote's usage_records from local truth after a
`ccg update usage --rebuild`, preserving other devices' rows.
"""
#region Imports
import typer
from rich.console import Console

from src.storage import get_db_path

#endregion


#region Command


def repair_command() -> None:
    """
    Rebuild the quack remote table from this device's corrected local data.

    A `ccg update usage --rebuild` rewrites local row identities, leaving the
    remote with stale rows that a normal push cannot replace (quack has no
    DELETE). This command recreates the remote usage_records table: rows for
    devices in this local database come from local truth; every other
    device's rows are preserved byte-for-byte. Nothing is lost - the entire
    pre-repair table is backed up to a local DuckDB file AND the preserved
    rows to a server-side table before anything is dropped.

    Avoid concurrent pushes from other devices while this runs. Devices not
    in this local database keep their (pre-fix) rows until each runs its own
    rebuild + repair.
    """
    console = Console()
    from src.storage.quack_remote import repair_remote

    db_path = get_db_path()
    if not db_path.exists():
        console.print("[red]Local database not found. Run 'ccg usage' first.[/red]")
        raise typer.Exit(1)

    try:
        with console.status(
            "[bold #ff8800]Repairing quack remote...", spinner="dots", spinner_style="#ff8800"
        ):
            result = repair_remote(db_path)
    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}[/red]")
        raise typer.Exit(1)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print("[green]Remote repaired[/green]")
    console.print(f"[dim]Local backup: {result['backup_path']}[/dim]")
    console.print(f"[dim]Server-side backup of preserved rows: remote.{result['keep_table']}[/dim]")
    for device in sorted(set(result["before"]) | set(result["after"])):
        b = result["before"].get(device, 0)
        a = result["after"].get(device, 0)
        marker = "replaced" if device in result["local_devices"] else "preserved"
        console.print(f"  {device}: {b:,} -> {a:,} ({marker})")
    console.print("[dim]Purge guard cleared; incremental pushes resume.[/dim]")


#endregion
