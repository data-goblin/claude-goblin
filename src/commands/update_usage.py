#region Imports
from rich.console import Console

from src.commands.limits import capture_limits
from src.config.settings import get_claude_jsonl_files
from src.config.user_config import get_storage_mode, get_tracking_mode
from src.data.jsonl_parser import parse_all_jsonl_files
from src.storage import api
#endregion


#region Functions


def run(console: Console) -> None:
    """
    Update usage database and fill in gaps with empty records.

    This command:
    1. Saves current usage data from JSONL files
    2. Fills in missing days with zero-usage records
    3. Ensures complete date coverage from earliest record to today

    Args:
        console: Rich console for output
    """
    try:
        tracking_mode = get_tracking_mode()

        # Save current snapshot (tokens)
        if tracking_mode in ["both", "tokens"]:
            jsonl_files = get_claude_jsonl_files()
            if jsonl_files:
                records = parse_all_jsonl_files(jsonl_files)
                if records:
                    saved_count = api.save_snapshot(records, storage_mode=get_storage_mode())
                    console.print(f"[green]Saved {saved_count} new token records[/green]")

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

        # Get database stats to determine date range
        db_stats = api.get_database_stats()
        if db_stats["total_records"] == 0:
            console.print("[yellow]No data to process.[/yellow]")
            return

        # Fill in gaps from oldest date to today
        from datetime import datetime
        today = datetime.now().date().strftime("%Y-%m-%d")
        filled_count = api.fill_empty_daily_snapshots(db_stats["oldest_date"], today)

        if filled_count > 0:
            console.print(f"[cyan]Filled {filled_count} empty days[/cyan]")

        # Show updated stats
        db_stats = api.get_database_stats()
        console.print(
            f"[green]Complete! Coverage: {db_stats['oldest_date']} to {db_stats['newest_date']}[/green]"
        )

    except Exception as e:
        console.print(f"[red]Error updating usage: {e}[/red]")
        import traceback
        traceback.print_exc()


#endregion
