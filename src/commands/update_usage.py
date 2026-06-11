#region Imports
from pathlib import Path
from typing import Optional

from rich.console import Console

from src.commands.limits import capture_limits
from src.config.settings import get_claude_jsonl_files
from src.config.user_config import get_extra_sources, get_storage_mode, get_tracking_mode
from src.data.jsonl_parser import parse_all_jsonl_files
from src.storage import api
#endregion


#region Functions


def run(console: Console) -> None:
    """
    Update usage database and fill in gaps with empty records.

    Incremental: only parses JSONL files whose mtime/size has changed since
    the last run (tracked in the file_metadata table). On a typical Stop-hook
    invocation, exactly one file is stale and a handful of new records get
    inserted.

    Args:
        console: Rich console for output
    """
    try:
        tracking_mode = get_tracking_mode()

        # Save current snapshot (tokens) -- incremental via get_stale_files
        if tracking_mode in ["both", "tokens"]:
            # Each source is (jsonl files, device overrides); None overrides
            # means this device's identity from config.
            sources: list[tuple[list[Path], Optional[dict]]] = []
            jsonl_files = get_claude_jsonl_files()
            if jsonl_files:
                sources.append((jsonl_files, None))
            for extra in get_extra_sources():
                extra_dir = Path(extra["path"])
                if extra_dir.is_dir():
                    extra_files = list(extra_dir.rglob("*.jsonl"))
                    if extra_files:
                        sources.append((extra_files, extra))

            all_files = [f for files, _ in sources for f in files]
            if all_files:
                # One stale/deleted pass over the union of all sources:
                # get_stale_files marks tracked paths missing from its input
                # as deleted, so separate per-source calls would evict each
                # other's file_metadata rows.
                stale_files, deleted_files = api.get_stale_files(all_files)
                stale_set = {str(f) for f in stale_files}

                for files, overrides in sources:
                    source_stale = [f for f in files if str(f) in stale_set]
                    if not source_stale:
                        continue
                    records = parse_all_jsonl_files(source_stale)
                    if records:
                        device_kwargs = {}
                        if overrides:
                            device_kwargs = {
                                "device_id": overrides["device_id"],
                                "device_name": overrides["device_name"],
                                "device_type": overrides["device_type"],
                            }
                        saved_count = api.save_snapshot(
                            records,
                            storage_mode=get_storage_mode(),
                            **device_kwargs,
                        )
                        source_label = f" ({overrides['device_name']})" if overrides else ""
                        console.print(f"[green]Saved {saved_count} new token records{source_label}[/green]")
                    for file_path in source_stale:
                        api.update_file_metadata(file_path, record_count=0)

                if deleted_files:
                    api.remove_deleted_file_metadata(deleted_files)

                if not stale_files and not deleted_files:
                    console.print("[dim]No new data to ingest[/dim]")

        # Capture and save limits
        if tracking_mode in ["both", "limits"]:
            limits = capture_limits()
            if limits and "error" not in limits:
                api.save_limits_snapshot(
                    session_pct=limits["session_pct"],
                    week_pct=limits["week_pct"],
                    opus_pct=limits["opus_pct"],
                    session_reset=limits["session_reset"],
                    week_reset=limits["week_reset"],
                    opus_reset=limits["opus_reset"],
                )
                console.print(f"[green]Saved limits snapshot (Session: {limits['session_pct']}%, Week: {limits['week_pct']}%, Opus: {limits['opus_pct']}%)[/green]")
            elif limits and "error" in limits:
                console.print(f"[yellow]⚠ {limits['message']}[/yellow]")
                console.print(f"[dim]Skipping limits tracking. Token tracking will continue.[/dim]")

        # Fill in date gaps so the heatmap is contiguous
        db_stats = api.get_database_stats()
        if db_stats["total_records"] == 0:
            console.print("[yellow]No data to process.[/yellow]")
            return

        from datetime import datetime
        today = datetime.now().date().strftime("%Y-%m-%d")
        filled_count = api.fill_empty_daily_snapshots(db_stats["oldest_date"], today)
        if filled_count > 0:
            console.print(f"[cyan]Filled {filled_count} empty days[/cyan]")

        db_stats = api.get_database_stats()
        console.print(
            f"[green]Complete! Coverage: {db_stats['oldest_date']} to {db_stats['newest_date']}[/green]"
        )

    except Exception as e:
        console.print(f"[red]Error updating usage: {e}[/red]")
        import traceback
        traceback.print_exc()


#endregion
