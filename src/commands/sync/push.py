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


#region Functions


def run_push(console: Console, force: bool = False, full: bool = False, strict: bool = True) -> None:
    """
    Validate sync config and push local records to the remote.

    strict=True raises typer.Exit(1) on configuration problems (interactive
    `ccg sync push`); strict=False skips them quietly so hook-driven flows
    no-op on hosts without a remote. Actual push failures always exit
    non-zero so wrapper logs capture them.
    """
    provider = get_sync_provider()
    if provider != "quack":
        if not strict:
            return
        console.print(f"[red]Sync provider is '{provider}', not 'quack'[/red]")
        console.print("[yellow]Run: ccg sync setup --provider quack[/yellow]")
        raise typer.Exit(1)

    storage_mode = get_storage_mode()
    if storage_mode != "full" and not force:
        if not strict:
            console.print("[dim]Skipping push: storage mode is 'aggregate'[/dim]")
            return
        console.print("[red]Storage mode is 'aggregate' - individual records not available[/red]")
        console.print("[yellow]Set full mode: ccg update usage --storage-mode full[/yellow]")
        console.print("[yellow]Or use --force to push daily_snapshots only[/yellow]")
        raise typer.Exit(1)

    db_path = get_db_path()
    if not db_path.exists():
        if not strict:
            return
        console.print("[red]Local database not found. Run 'ccg usage' first.[/red]")
        raise typer.Exit(1)

    try:
        from src.storage.quack_remote import push_to_remote

        with console.status("[bold #ff8800]Pushing to remote...", spinner="dots", spinner_style="#ff8800"):
            result = push_to_remote(db_path, full=full)

        if result.get("skipped"):
            console.print("[dim]Nothing new to push (watermark up to date)[/dim]")
        else:
            console.print(f"[green]Pushed {result['new_records']:,} new records to remote[/green]")
            if result.get("remote_total") is not None:
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


#region Command


def push_command(
    force: bool = typer.Option(False, "--force", "-f", help="Push even if storage mode is 'aggregate'"),
    full: bool = typer.Option(False, "--full", help="Ignore the push watermark and reconcile against all remote keys"),
):
    """
    Push local usage records to the remote DuckDB server.

    Syncs new local usage_records, limits, and pricing to the configured
    remote. Deduplicates by (session_id, message_uuid). A local watermark
    keeps routine pushes incremental; use --full to reconcile everything
    (e.g. after remote rows were removed manually). --full still advances
    the watermark to the current local maximum afterwards.

    Requires:
    - Sync provider set to 'quack' (ccg sync setup --provider quack)
    - Storage mode 'full' for individual record sync (--force to override)
    - Remote server running and reachable
    """
    console = Console()
    run_push(console, force=force, full=full, strict=True)


#endregion
