#region Imports
import sys
import time
from pathlib import Path

from rich.console import Console

from src.aggregation.daily_stats import aggregate_all
from src.commands.limits import capture_limits
from src.config.settings import (
    DEFAULT_REFRESH_INTERVAL,
    get_claude_jsonl_files,
)
from src.config.user_config import get_storage_mode, get_tracking_mode
from src.data.jsonl_parser import parse_all_jsonl_files
from src.storage.snapshot_db import (
    get_database_stats,
    load_historical_records,
    save_limits_snapshot,
    save_snapshot,
)
from src.visualization.dashboard import render_dashboard
#endregion


#region Functions


def run(console: Console, live: bool = False, fast: bool = False, anon: bool = False) -> None:
    """
    Handle the usage command.

    Loads Claude Code usage data and displays a dashboard with GitHub-style
    activity graph and statistics. Supports live refresh mode.

    Args:
        console: Rich console for output
        live: Enable auto-refresh mode (default: False)
        fast: Skip limits fetching for faster rendering (default: False)
        anon: Anonymize project names to project-001, project-002, etc (default: False)

    Exit:
        Exits with status 0 on success, 1 on error
    """
    # Check sys.argv for backward compatibility (hooks still use old style)
    run_live = live or "--live" in sys.argv
    skip_limits = fast or "--fast" in sys.argv
    anonymize = anon or "--anon" in sys.argv

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
            _run_live_dashboard(jsonl_files, console, skip_limits, anonymize)
        else:
            _display_dashboard(jsonl_files, console, skip_limits, anonymize)

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


def _run_live_dashboard(jsonl_files: list[Path], console: Console, skip_limits: bool = False, anonymize: bool = False) -> None:
    """
    Run dashboard with auto-refresh.

    Args:
        jsonl_files: List of JSONL files to parse
        console: Rich console for output
        skip_limits: Skip limits fetching for faster rendering
        anonymize: Anonymize project names
    """
    console.print(
        f"[dim]Auto-refreshing every {DEFAULT_REFRESH_INTERVAL} seconds. "
        "Press Ctrl+C to exit.[/dim]\n"
    )

    while True:
        try:
            _display_dashboard(jsonl_files, console, skip_limits, anonymize)
            time.sleep(DEFAULT_REFRESH_INTERVAL)
        except KeyboardInterrupt:
            raise


def _display_dashboard(jsonl_files: list[Path], console: Console, skip_limits: bool = False, anonymize: bool = False) -> None:
    """
    Ingest JSONL data and display dashboard.

    This performs two steps:
    1. Ingestion: Read JSONL files and save to DB (with deduplication)
    2. Display: Read from DB and render dashboard

    Args:
        jsonl_files: List of JSONL files to parse
        console: Rich console for output
        skip_limits: Skip ALL updates, read directly from DB (fast mode)
        anonymize: Anonymize project names to project-001, project-002, etc
    """
    from src.storage.snapshot_db import get_latest_limits, DEFAULT_DB_PATH, get_database_stats

    # Check if database exists when using --fast
    if skip_limits and not DEFAULT_DB_PATH.exists():
        console.clear()
        console.print("[red]Error: Cannot use --fast flag without existing database.[/red]")
        console.print("[yellow]Run 'ccg usage' (without --fast) first to create the database.[/yellow]")
        return

    # Update data unless in fast mode
    if not skip_limits:
        # Step 1: Update usage data
        with console.status("[bold #ff8800]Updating usage data...", spinner="dots", spinner_style="#ff8800"):
            current_records = parse_all_jsonl_files(jsonl_files)

            # Save to database (with automatic deduplication via UNIQUE constraint)
            if current_records:
                save_snapshot(current_records, storage_mode=get_storage_mode())

        # Step 2: Update limits data (if enabled)
        tracking_mode = get_tracking_mode()
        if tracking_mode in ["both", "limits"]:
            with console.status("[bold #ff8800]Updating usage limits...", spinner="dots", spinner_style="#ff8800"):
                limits = capture_limits()
                if limits and "error" not in limits:
                    save_limits_snapshot(
                        session_pct=limits["session_pct"],
                        week_pct=limits["week_pct"],
                        opus_pct=limits["opus_pct"],
                        session_reset=limits["session_reset"],
                        week_reset=limits["week_reset"],
                        opus_reset=limits["opus_reset"],
                    )
                elif limits and "error" in limits:
                    console.print(f"[yellow]⚠ {limits['message']}[/yellow]")
                    console.print(f"[dim]Skipping limits tracking. Token tracking will continue.[/dim]")

    # Step 3: Prepare dashboard from database
    with console.status("[bold #ff8800]Preparing dashboard...", spinner="dots", spinner_style="#ff8800"):
        all_records = load_historical_records()

        # Get latest limits from DB (if we saved them above or if they exist)
        limits_from_db = get_latest_limits()

    if not all_records:
        console.clear()
        console.print(
            "[yellow]No usage data found in database. Run --update-usage to ingest data.[/yellow]"
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

    # Render dashboard with limits from DB (no live fetch needed)
    render_dashboard(stats, all_records, console, skip_limits=True, clear_screen=False, date_range=date_range, limits_from_db=limits_from_db, fast_mode=skip_limits)


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
