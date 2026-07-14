#region Imports
import sys
import time
from pathlib import Path

from rich.console import Console

from src.aggregation.daily_stats import aggregate_all
from src.commands.update_usage import ingest_token_usage
from src.config.settings import (
    DEFAULT_REFRESH_INTERVAL,
    get_claude_jsonl_files,
)
from src.data.jsonl_parser import parse_all_jsonl_files
from src.storage import api
from src.storage.api import load_historical_records
from src.visualization.dashboard import render_dashboard

#endregion


#region Functions


def run(console: Console, live: bool = False, fast: bool = False, anon: bool = False, force: bool = False) -> None:
    """
    Handle the usage command.

    Loads Claude Code usage data and displays a dashboard with GitHub-style
    activity graph and statistics. Supports live refresh mode.

    Args:
        console: Rich console for output
        live: Enable auto-refresh mode (default: False)
        fast: Skip all updates, read directly from DB (default: False)
        anon: Anonymize project names to project-001, project-002, etc (default: False)
        force: Force re-parse all files, ignoring incremental cache (default: False)

    Exit:
        Exits with status 0 on success, 1 on error
    """
    # Check sys.argv for backward compatibility (hooks still use old style)
    run_live = live or "--live" in sys.argv
    fast_mode = fast or "--fast" in sys.argv
    anonymize = anon or "--anon" in sys.argv
    force_reparse = force or "--force" in sys.argv

    try:
        with console.status("[bold #ff8800]Loading Claude Code usage data...", spinner="dots", spinner_style="#ff8800"):
            jsonl_files = get_claude_jsonl_files()

        if not jsonl_files:
            console.print(
                "[yellow]No Claude Code data found. "
                "Make sure you've used Claude Code at least once.[/yellow]"
            )
            return

        console.print(f"[dim]Found {len(jsonl_files)} session files[/dim]", end="")

        # Run with or without live refresh
        if run_live:
            _run_live_dashboard(jsonl_files, console, fast_mode, anonymize, force_reparse)
        else:
            _display_dashboard(jsonl_files, console, fast_mode, anonymize, force_reparse)

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[cyan]Exiting...[/cyan]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def _run_live_dashboard(jsonl_files: list[Path], console: Console, fast_mode: bool = False, anonymize: bool = False, force: bool = False) -> None:
    """
    Run dashboard with auto-refresh.

    Args:
        jsonl_files: List of JSONL files to parse
        console: Rich console for output
        fast_mode: Skip all updates, read directly from DB
        anonymize: Anonymize project names
        force: Force re-parse all files on first run only.
               Note: In live mode, --force only applies to the initial refresh.
               Subsequent refreshes use incremental parsing for efficiency.
    """
    if force:
        console.print(
            "[yellow]Note: --force only applies to the first refresh in live mode.[/yellow]"
        )
        console.print(
            "[yellow]Subsequent refreshes will use incremental parsing.[/yellow]\n"
        )

    console.print(
        f"[dim]Auto-refreshing every {DEFAULT_REFRESH_INTERVAL} seconds. "
        "Press Ctrl+C to exit.[/dim]\n"
    )

    first_run = True
    while True:
        try:
            # Only force on first run in live mode (documented behavior)
            _display_dashboard(jsonl_files, console, fast_mode, anonymize, force and first_run)
            first_run = False
            time.sleep(DEFAULT_REFRESH_INTERVAL)
        except KeyboardInterrupt:
            raise


def _display_dashboard(jsonl_files: list[Path], console: Console, fast_mode: bool = False, anonymize: bool = False, force: bool = False) -> None:
    """
    Ingest JSONL data and display dashboard.

    This performs two steps:
    1. Ingestion: Read JSONL files and save to DB (with deduplication)
    2. Display: Parse JSONL for detailed view, use DB for historical heatmap

    Args:
        jsonl_files: List of JSONL files to parse
        console: Rich console for output
        fast_mode: Skip ALL updates, read directly from DB
        anonymize: Anonymize project names to project-001, project-002, etc
        force: Force re-parse all files, ignoring incremental cache
    """
    # Check if database exists when using --fast
    if fast_mode and not api.current_db_path().exists():
        console.clear()
        console.print("[red]Error: Cannot use --fast flag without existing database.[/red]")
        console.print("[yellow]Run 'ccg usage' (without --fast) first to create the database.[/yellow]")
        return

    current_records = []

    # Update data unless in fast mode
    if not fast_mode:
        # Step 1: Update usage data via the shared ingest (incremental,
        # covers extra_sources too)
        if force:
            console.print("\n[yellow]Force mode: reparsing all files (this may take a moment)[/yellow]")
        with console.status("[bold #ff8800]Updating changed files...", spinner="dots", spinner_style="#ff8800"):
            ingest_token_usage(console, force=force, verbose=False)

        # Step 2: Parse ALL JSONL files for detailed model/branch/project breakdown
        # This ensures we always have granular data regardless of storage mode
        if not current_records:
            with console.status("[bold #ff8800]Loading usage data...", spinner="dots", spinner_style="#ff8800"):
                current_records = parse_all_jsonl_files(jsonl_files)

    # Step 3: Prepare dashboard
    with console.status("[bold #ff8800]Preparing dashboard...", spinner="dots", spinner_style="#ff8800"):
        # In fast mode, load from DB (aggregate records)
        # Otherwise, use parsed JSONL records for detailed breakdowns
        if fast_mode:
            all_records = load_historical_records()
        else:
            all_records = current_records if current_records else load_historical_records()

    if not all_records:
        console.clear()
        console.print(
            "[yellow]No usage data found. Make sure you have Claude Code session files.[/yellow]"
        )
        return

    # Clear screen before displaying dashboard
    console.clear()

    # Get date range for footer
    dates = sorted(set(r.date_key for r in all_records))
    date_range = None
    if dates:
        date_range = f"{dates[0]} to {dates[-1]}"

    # Anonymize project names if requested
    if anonymize:
        all_records = _anonymize_projects(all_records)

    # Aggregate statistics
    stats = aggregate_all(all_records)

    render_dashboard(stats, all_records, console, clear_screen=False, date_range=date_range, fast_mode=fast_mode)


def run_remote(console: Console, anon: bool = False) -> None:
    """
    Display usage dashboard from the remote DuckDB server.

    Queries the remote for cross-device aggregate data and renders
    the same dashboard view.
    """
    try:
        from src.storage.quack_remote import (
            load_historical_records as remote_load,
        )

        with console.status("[bold #ff8800]Connecting to remote...", spinner="dots", spinner_style="#ff8800"):
            all_records = remote_load()

        if not all_records:
            console.print("[yellow]No usage data on remote. Push first with: ccg sync push[/yellow]")
            return

        console.clear()

        dates = sorted(set(r.date_key for r in all_records))
        date_range = f"{dates[0]} to {dates[-1]}" if dates else None

        if anon:
            all_records = _anonymize_projects(all_records)

        stats = aggregate_all(all_records)

        from src.visualization.dashboard import render_dashboard
        render_dashboard(
            stats, all_records, console,
            clear_screen=False,
            date_range=date_range,
            fast_mode=True,
        )
        console.print("\n[dim]Source: remote (cross-device aggregate)[/dim]")

    except ImportError:
        console.print("[red]DuckDB not installed. Install with: uv pip install claude-goblin[duckdb][/red]")
    except RuntimeError as e:
        console.print(f"[red]Remote connection failed: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _anonymize_projects(records: list) -> list:
    """
    Anonymize project folder names by ranking them by total tokens and replacing
    with project-001, project-002, etc (where project-001 is the highest usage).

    Args:
        records: List of UsageRecord objects

    Returns:
        List of UsageRecord objects with anonymized folder names
    """
    from collections import defaultdict
    from dataclasses import replace

    # Calculate total tokens per project
    project_totals = defaultdict(int)
    for record in records:
        if record.token_usage:
            project_totals[record.folder] += record.token_usage.total_tokens

    # Sort projects by total tokens (descending) and create mapping
    sorted_projects = sorted(project_totals.items(), key=lambda x: x[1], reverse=True)
    project_mapping = {
        folder: f"project-{str(i+1).zfill(3)}"
        for i, (folder, _) in enumerate(sorted_projects)
    }

    # Replace folder names in records
    anonymized_records = []
    for record in records:
        anonymized_records.append(
            replace(record, folder=project_mapping.get(record.folder, record.folder))
        )

    return anonymized_records


#endregion
