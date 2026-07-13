#region Imports
from rich.console import Console

from src.aggregation.usage_limits import UsageLimits

#endregion


#region Functions


def render_usage_limits(limits: UsageLimits, console: Console) -> None:
    """
    Render usage limits as simple percentages with reset times.

    Displays:
    - Session: X% (resets at TIME)
    - Week: X% (resets on DATE)
    - Opus: X% (resets on DATE) [if applicable]

    Args:
        limits: UsageLimits object with usage data
        console: Rich console for output

    Common failure modes:
        - None values are handled gracefully
        - Percentages over 100% are shown as-is (no capping)
    """
    console.print()

    # Session
    session_pct = limits.session_percentage
    reset_str = ""
    if limits.session_reset_time:
        local_time = limits.session_reset_time.astimezone()
        reset_str = local_time.strftime("%I:%M%p").lstrip('0')

    console.print(f"[bold cyan]Session:[/bold cyan] {session_pct:.0f}% [dim](resets {reset_str})[/dim]")

    # Week (all models)
    week_pct = limits.week_percentage
    week_reset_str = ""
    if limits.week_reset_time:
        local_time = limits.week_reset_time.astimezone()
        week_reset_str = local_time.strftime("%b %d").replace(' 0', ' ')

    console.print(f"[bold cyan]Week:[/bold cyan]    {week_pct:.0f}% [dim](resets {week_reset_str})[/dim]")

    # Opus (only for Max plans)
    if limits.opus_limit > 0:
        opus_pct = limits.opus_percentage
        console.print(f"[bold cyan]Opus:[/bold cyan]    {opus_pct:.0f}% [dim](resets {week_reset_str})[/dim]")

    console.print()


#endregion
