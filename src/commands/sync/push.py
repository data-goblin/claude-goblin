"""
Sync push command for Claude Goblin.

Pushes local usage records to the remote DuckDB via Quack protocol.
"""
#region Imports
import typer
from rich.console import Console

from src.config.user_config import get_sync_provider, get_storage_mode
from src.storage import get_db_path
#endregion


#region Command


def push_command(
    force: bool = typer.Option(False, "--force", "-f", help="Push even if storage mode is 'aggregate'"),
):
    """
    Push local usage records to the remote DuckDB server.

    Syncs all local usage_records, daily_snapshots, limits, and pricing
    to the configured remote. Deduplicates by (session_id, message_uuid).

    Requires:
    - Sync provider set to 'quack' (ccg sync setup --provider quack)
    - Storage mode 'full' for individual record sync (--force to override)
    - Remote server running and reachable
    """
    console = Console()

    provider = get_sync_provider()
    if provider != "quack":
        console.print(f"[red]Sync provider is '{provider}', not 'quack'[/red]")
        console.print("[yellow]Run: ccg sync setup --provider quack[/yellow]")
        raise typer.Exit(1)

    storage_mode = get_storage_mode()
    if storage_mode != "full" and not force:
        console.print("[red]Storage mode is 'aggregate' - individual records not available[/red]")
        console.print("[yellow]Set full mode: ccg update usage --storage-mode full[/yellow]")
        console.print("[yellow]Or use --force to push daily_snapshots only[/yellow]")
        raise typer.Exit(1)

    db_path = get_db_path()
    if not db_path.exists():
        console.print("[red]Local database not found. Run 'ccg usage' first.[/red]")
        raise typer.Exit(1)

    try:
        from src.storage.quack_remote import push_to_remote

        with console.status("[bold #ff8800]Pushing to remote...", spinner="dots", spinner_style="#ff8800"):
            result = push_to_remote(db_path)

        console.print(f"[green]Pushed {result['new_records']:,} new records to remote[/green]")
        console.print(f"[dim]Remote total: {result['remote_total']:,} records from {result['devices']} device(s)[/dim]")

    except ImportError:
        console.print("[red]DuckDB not installed. Install with: uv pip install claude-goblin[duckdb][/red]")
        raise typer.Exit(1)
    except RuntimeError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Push failed: {e}[/red]")
        raise typer.Exit(1)


#endregion
