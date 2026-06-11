#region Imports
import sys
from datetime import datetime

from rich.console import Console

from src.commands.limits import capture_limits
from src.commands.update_usage import ingest_token_usage
from src.config.user_config import get_tracking_mode
from src.storage import api
from src.storage.api import (
    get_database_stats,
    get_text_analysis_stats,
    save_limits_snapshot,
)
#endregion


#region Functions


def run(console: Console, fast: bool = False, force: bool = False) -> None:
    """
    Show statistics about the historical database.

    Displays comprehensive statistics including:
    - Summary: total tokens, prompts, responses, sessions, days tracked
    - Cost analysis: estimated API costs vs Max Plan costs
    - Averages: tokens per session/response, cost per session/response
    - Text analysis: prompt length, politeness markers, phrase counts
    - Usage by model: token distribution across different models

    Args:
        console: Rich console for output
        fast: Skip updates, read directly from database (default: False)
        force: Force re-parse all files, ignoring incremental cache (default: False)
    """
    # Check for flags in sys.argv for backward compatibility
    fast_mode = fast or "--fast" in sys.argv
    force_mode = force or "--force" in sys.argv

    # Check if database exists when using --fast
    if fast_mode and not api.current_db_path().exists():
        console.print("[red]Error: Cannot use --fast flag without existing database.[/red]")
        console.print("[yellow]Run 'ccg stats' (without --fast) first to create the database.[/yellow]")
        return

    # If fast mode, show warning with last update timestamp
    if fast_mode:
        db_stats_temp = get_database_stats()
        if db_stats_temp.get("newest_timestamp"):
            # Format ISO timestamp to be more readable
            timestamp_str = db_stats_temp["newest_timestamp"]
            try:
                dt = datetime.fromisoformat(timestamp_str)
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                console.print(f"[bold red]⚠ Fast mode: Reading from last update ({formatted_time})[/bold red]\n")
            except (ValueError, AttributeError):
                console.print(f"[bold red]⚠ Fast mode: Reading from last update ({timestamp_str})[/bold red]\n")
        else:
            console.print("[bold red]⚠ Fast mode: Reading from database (no timestamp available)[/bold red]\n")

    # Update data unless in fast mode
    if not fast_mode:
        # Step 1: Ingestion - parse JSONL and save to DB (incremental)
        if force_mode:
            console.print("[yellow]Force mode: reparsing all files (this may take a moment)[/yellow]")
        with console.status("[bold #ff8800]Updating changed files...", spinner="dots", spinner_style="#ff8800"):
            ingest_token_usage(console, force=force_mode, verbose=False)

        # Step 2: Update limits data (if enabled and working)
        # NOTE: Limits tracking is currently disabled due to Claude Code format changes
        tracking_mode = get_tracking_mode()
        if tracking_mode in ["both", "limits"]:
            limits = capture_limits()
            if limits and "error" not in limits:
                with console.status("[bold #ff8800]Updating usage limits...", spinner="dots", spinner_style="#ff8800"):
                    save_limits_snapshot(
                        session_pct=limits["session_pct"],
                        week_pct=limits["week_pct"],
                        opus_pct=limits["opus_pct"],
                        session_reset=limits["session_reset"],
                        week_reset=limits["week_reset"],
                        opus_reset=limits["opus_reset"],
                    )
            # Silently skip if disabled

    # Step 3: Display stats from DB
    db_stats = get_database_stats()

    if db_stats["total_records"] == 0 and db_stats["total_prompts"] == 0:
        console.print("[yellow]No historical data found. Run ccg usage to start tracking.[/yellow]")
        return

    console.print("[bold cyan]Claude Code Usage Statistics[/bold cyan]\n")

    # Summary Statistics
    console.print("[bold]Summary[/bold]")
    console.print(f"  Total Tokens:        {db_stats['total_tokens']:>15,}")
    console.print(f"  Total Prompts:       {db_stats['total_prompts']:>15,}")
    console.print(f"  Total Responses:     {db_stats['total_responses']:>15,}")
    console.print(f"  Total Sessions:      {db_stats['total_sessions']:>15,}")
    console.print(f"  Days Tracked:        {db_stats['total_days']:>15,}")
    console.print(f"  Date Range:          {db_stats['oldest_date']} to {db_stats['newest_date']}")

    # Cost Summary (if using API pricing)
    if db_stats['total_cost'] > 0:
        # Calculate actual months covered from date range
        start_date = datetime.strptime(db_stats['oldest_date'], "%Y-%m-%d")
        end_date = datetime.strptime(db_stats['newest_date'], "%Y-%m-%d")

        # Count unique months covered
        months_covered = set()
        current = start_date
        while current <= end_date:
            months_covered.add((current.year, current.month))
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)

        num_months = len(months_covered)
        plan_cost = num_months * 200.0  # $200/month Max Plan
        savings = db_stats['total_cost'] - plan_cost

        console.print(f"\n[bold]Cost Analysis[/bold]")
        console.print(f"  Est. Cost (if using API): ${db_stats['total_cost']:>10,.2f}")
        console.print(f"  Plan Cost:           ${plan_cost:>14,.2f} ({num_months} month{'s' if num_months > 1 else ''} @ $200/mo)")

        if savings > 0:
            console.print(f"  You Saved:           ${savings:>14,.2f} (vs API)")
        else:
            overpaid = abs(savings)
            console.print(f"  Plan Costs More:     ${overpaid:>14,.2f}")
            console.print(f"  [dim]Light usage - API would be cheaper[/dim]")

    # Averages
    console.print(f"\n[bold]Averages[/bold]")
    console.print(f"  Tokens per Session:  {db_stats['avg_tokens_per_session']:>15,}")
    console.print(f"  Tokens per Response: {db_stats['avg_tokens_per_response']:>15,}")
    if db_stats['total_cost'] > 0:
        console.print(f"  Cost per Session:    ${db_stats['avg_cost_per_session']:>14,.2f}")
        console.print(f"  Cost per Response:   ${db_stats['avg_cost_per_response']:>14,.4f}")

    # Text Analysis (from current JSONL files)
    text_stats = get_text_analysis_stats()

    if text_stats["avg_user_prompt_chars"] > 0:
        console.print(f"\n[bold]Text Analysis[/bold]")
        console.print(f"  Avg Prompt Length:   {text_stats['avg_user_prompt_chars']:>15,} chars")
        console.print(f"  User Swears:         {text_stats['user_swears']:>15,}")
        console.print(f"  Claude Swears:       {text_stats['assistant_swears']:>15,}")
        console.print(f"  User Thanks:         {text_stats['user_thanks']:>15,}")
        console.print(f"  User Please:         {text_stats['user_please']:>15,}")
        console.print(f"  Claude \"Perfect!\"/\"Excellent!\": {text_stats['perfect_count']:>10,}")
        console.print(f"  Claude \"You're absolutely right!\": {text_stats['absolutely_right_count']:>6,}")

    # Tokens by Model
    if db_stats["tokens_by_model"]:
        console.print(f"\n[bold]Usage by Model[/bold]")
        for model, tokens in db_stats["tokens_by_model"].items():
            percentage = (tokens / db_stats['total_tokens'] * 100) if db_stats['total_tokens'] > 0 else 0
            cost = db_stats["cost_by_model"].get(model, 0.0)
            if cost > 0:
                console.print(f"  {model:30s} {tokens:>15,} ({percentage:5.1f}%) ${cost:>10,.2f}")
            else:
                console.print(f"  {model:30s} {tokens:>15,} ({percentage:5.1f}%)")

    # Database Info
    console.print(f"\n[dim]Database: {api.current_db_path()}[/dim]")
    if db_stats["total_records"] > 0:
        console.print(f"[dim]Detail records: {db_stats['total_records']:,} (full analytics mode)[/dim]")
    else:
        console.print(f"[dim]Storage mode: aggregate (daily totals only)[/dim]")


def run_remote(console: Console) -> None:
    """
    Show statistics from the remote DuckDB server (cross-device aggregate).
    """
    try:
        from src.storage.quack_remote import get_database_stats as remote_stats

        with console.status("[bold #ff8800]Connecting to remote...", spinner="dots", spinner_style="#ff8800"):
            db_stats = remote_stats()

        if db_stats["total_records"] == 0 and db_stats["total_prompts"] == 0:
            console.print("[yellow]No data on remote. Push first with: ccg sync push[/yellow]")
            return

        console.print("[bold cyan]Claude Code Usage Statistics (Remote)[/bold cyan]\n")

        console.print("[bold]Summary[/bold]")
        console.print(f"  Total Tokens:        {db_stats['total_tokens']:>15,}")
        console.print(f"  Total Prompts:       {db_stats['total_prompts']:>15,}")
        console.print(f"  Total Responses:     {db_stats['total_responses']:>15,}")
        console.print(f"  Total Sessions:      {db_stats['total_sessions']:>15,}")
        console.print(f"  Days Tracked:        {db_stats['total_days']:>15,}")
        console.print(f"  Date Range:          {db_stats['oldest_date']} to {db_stats['newest_date']}")

        if db_stats['total_cost'] > 0:
            start_date = datetime.strptime(db_stats['oldest_date'], "%Y-%m-%d")
            end_date = datetime.strptime(db_stats['newest_date'], "%Y-%m-%d")
            months_covered = set()
            current = start_date
            while current <= end_date:
                months_covered.add((current.year, current.month))
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    current = current.replace(month=current.month + 1, day=1)
            num_months = len(months_covered)
            plan_cost = num_months * 200.0
            savings = db_stats['total_cost'] - plan_cost

            console.print(f"\n[bold]Cost Analysis[/bold]")
            console.print(f"  Est. Cost (if using API): ${db_stats['total_cost']:>10,.2f}")
            console.print(f"  Plan Cost:           ${plan_cost:>14,.2f} ({num_months} month{'s' if num_months > 1 else ''} @ $200/mo)")
            if savings > 0:
                console.print(f"  You Saved:           ${savings:>14,.2f} (vs API)")
            else:
                console.print(f"  Plan Costs More:     ${abs(savings):>14,.2f}")

        console.print(f"\n[bold]Averages[/bold]")
        console.print(f"  Tokens per Session:  {db_stats['avg_tokens_per_session']:>15,}")
        console.print(f"  Tokens per Response: {db_stats['avg_tokens_per_response']:>15,}")
        if db_stats['total_cost'] > 0:
            console.print(f"  Cost per Session:    ${db_stats['avg_cost_per_session']:>14,.2f}")
            console.print(f"  Cost per Response:   ${db_stats['avg_cost_per_response']:>14,.4f}")

        if db_stats["tokens_by_model"]:
            console.print(f"\n[bold]Usage by Model[/bold]")
            for model, tokens in db_stats["tokens_by_model"].items():
                pct = (tokens / db_stats['total_tokens'] * 100) if db_stats['total_tokens'] > 0 else 0
                cost = db_stats["cost_by_model"].get(model, 0.0)
                if cost > 0:
                    console.print(f"  {model:30s} {tokens:>15,} ({pct:5.1f}%) ${cost:>10,.2f}")
                else:
                    console.print(f"  {model:30s} {tokens:>15,} ({pct:5.1f}%)")

        console.print(f"\n[dim]Source: remote (cross-device aggregate)[/dim]")

    except ImportError:
        console.print("[red]DuckDB not installed. Install with: uv pip install claude-goblin[duckdb][/red]")
    except RuntimeError as e:
        console.print(f"[red]Remote connection failed: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


#endregion
