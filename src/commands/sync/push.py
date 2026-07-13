"""
Sync push command for Claude Goblin.

Pushes local usage records to every configured sink (quack DuckDB remote,
OneLake lakehouse).
"""
#region Imports
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from src.config.user_config import get_storage_mode, get_sync_providers
from src.storage import get_db_path

#endregion


#region Functions


_PUSHABLE_PROVIDERS = ("quack", "onelake")


def _push_one(provider: str, db_path: Path, full: bool, respect_interval: bool) -> dict[str, Any]:
    """Dispatch a single sink's push; returns its result dict."""
    if provider == "quack":
        from src.storage.quack_remote import push_to_remote
        return push_to_remote(db_path, full=full)
    from src.storage.onelake_remote import push_to_onelake
    return push_to_onelake(db_path, full=full, respect_interval=respect_interval)


def run_push(console: Console, force: bool = False, full: bool = False, strict: bool = True) -> None:
    """
    Validate sync config and push local records to every configured sink.

    strict=True raises typer.Exit(1) on configuration problems (interactive
    `ccg sync push`); strict=False skips them quietly so hook-driven flows
    no-op on hosts without a remote. Sinks are isolated: one failing does not
    block the others, but any real failure still exits non-zero so wrapper
    logs capture it. Hook-driven (strict=False) OneLake pushes respect the
    min-push-interval throttle; explicit pushes do not.
    """
    providers = [p for p in get_sync_providers() if p in _PUSHABLE_PROVIDERS]
    if not providers:
        if not strict:
            return
        console.print("[red]No pushable sync provider configured[/red]")
        console.print("[yellow]Run: ccg sync setup --provider quack (or onelake)[/yellow]")
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

    failures = 0
    for provider in providers:
        try:
            with console.status(
                f"[bold #ff8800]Pushing to {provider}...", spinner="dots", spinner_style="#ff8800"
            ):
                result = _push_one(db_path=db_path, provider=provider, full=full, respect_interval=not strict)

            if result.get("skipped"):
                console.print(f"[dim]{provider}: nothing new to push[/dim]")
            else:
                console.print(f"[green]{provider}: pushed {result['new_records']:,} new records[/green]")
                if result.get("remote_total") is not None:
                    console.print(
                        f"[dim]{provider} total: {result['remote_total']:,} records "
                        f"from {result['devices']} device(s)[/dim]"
                    )
        except ImportError as e:
            failures += 1
            console.print(f"[red]{provider}: missing dependency ({e})[/red]")
        except RuntimeError as e:
            failures += 1
            console.print(f"[red]{provider}: {e}[/red]")
        except Exception as e:
            failures += 1
            console.print(f"[red]{provider}: push failed: {e}[/red]")

    if failures:
        raise typer.Exit(1)


#endregion


#region Command


def push_command(
    force: bool = typer.Option(False, "--force", "-f", help="Push even if storage mode is 'aggregate'"),
    full: bool = typer.Option(False, "--full", help="Ignore the push watermark and reconcile against all remote keys"),
    quack_purged: bool = typer.Option(
        False, "--quack-purged",
        help="Confirm the quack remote was purged after a --rebuild; clears the push guard",
    ),
) -> None:
    """
    Push local usage records to every configured sync sink.

    Syncs new local usage_records, limits, and pricing to each sink in
    sync_providers (quack DuckDB remote, OneLake lakehouse). Deduplicates by
    (session_id, message_uuid). A per-sink watermark keeps routine pushes
    incremental; use --full to reconcile everything (e.g. after remote rows
    were removed manually). --full still advances the watermarks to the
    current local maximum afterwards.

    Requires:
    - At least one provider configured (ccg sync setup --provider quack|onelake)
    - Storage mode 'full' for individual record sync (--force to override)
    - The sink reachable (quack server up / az login for OneLake)
    """
    console = Console()
    if quack_purged:
        from src.storage.duckdb_backend import set_sync_state
        from src.storage.quack_remote import QUACK_PURGE_KEY
        set_sync_state(QUACK_PURGE_KEY, "0", db_path=get_db_path())
        console.print("[green]Quack purge guard cleared[/green]")
    run_push(console, force=force, full=full, strict=True)


#endregion
