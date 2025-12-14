#region Imports
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.aggregation.daily_stats import AggregatedStats, DailyStats
#endregion


#region Constants
# Claude UI color scheme
CLAUDE_BG = "#262624"
CLAUDE_TEXT = "#FAF9F5"
CLAUDE_TEXT_SECONDARY = "#C2C0B7"
CLAUDE_DARK_GREY = "grey15"  # Past days with no activity
CLAUDE_LIGHT_GREY = "grey50"  # Future days

# Claude orange base color (fully bright)
CLAUDE_ORANGE_RGB = (203, 123, 93)  # #CB7B5D

# Dot sizes for terminal visualization (smallest to largest)
DOT_SIZES = [" ", "·", "•", "●", "⬤"]  # Empty space for 0, then dots of increasing size

DAYS_OF_WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
#endregion


#region Helper Functions
def _parse_path_parts(path_str: str) -> list[str]:
    """Parse path into parts, handling both Unix and Windows separators."""
    if "\\" in path_str or (len(path_str) > 1 and path_str[1] == ":"):
        return list(PureWindowsPath(path_str).parts)
    return list(PurePosixPath(path_str).parts)


def _shorten_path(path_str: str, max_parts: int = 2) -> str:
    """Shorten a path to show only the last N parts, cross-platform."""
    parts = _parse_path_parts(path_str)
    if len(parts) > max_parts:
        return "/".join(parts[-max_parts:])
    return path_str
#endregion


#region Functions


def render_activity_graph(stats: AggregatedStats, console: Console) -> None:
    """
    Render a GitHub-style activity graph to the console.

    Displays a heatmap of token usage over the past 365 days,
    along with summary statistics.

    Args:
        stats: Aggregated statistics to visualize
        console: Rich console instance for rendering
    """
    # Create the main layout
    layout = _create_layout(stats)

    # Render to console
    console.clear()
    console.print(layout)


def _create_layout(stats: AggregatedStats) -> Group:
    """
    Create the complete layout with graph and statistics.

    Args:
        stats: Aggregated statistics

    Returns:
        Rich Group containing all visualization elements
    """
    # Create header
    header = _create_header(stats.overall_totals, stats.daily_stats)

    # Create timeline view
    timeline = _create_timeline_view(stats.daily_stats)

    # Create statistics table
    stats_table = _create_stats_table(stats.overall_totals)

    # Create breakdown tables
    breakdown = _create_breakdown_tables(stats.overall_totals)

    return Group(
        header,
        Text(""),  # Blank line
        timeline,
        Text(""),  # Blank line
        stats_table,
        Text(""),  # Blank line
        breakdown,
    )


def _create_header(overall: DailyStats, daily_stats: dict[str, DailyStats]) -> Panel:
    """
    Create header panel with title and key metrics.

    Args:
        overall: Overall statistics
        daily_stats: Dictionary of daily statistics to determine date range

    Returns:
        Rich Panel with header information
    """
    # Get date range
    if daily_stats:
        dates = sorted(daily_stats.keys())
        date_range_str = f"{dates[0]} to {dates[-1]}"
    else:
        date_range_str = "No data"

    header_text = Text()
    header_text.append("Claude Code Usage Tracker", style="bold cyan")
    header_text.append(f"  ({date_range_str})", style="dim")
    header_text.append("\n")
    header_text.append(f"Total Tokens: ", style="white")
    header_text.append(f"{overall.total_tokens:,}", style="bold yellow")
    header_text.append(" | ", style="dim")
    header_text.append(f"Prompts: ", style="white")
    header_text.append(f"{overall.total_prompts:,}", style="bold yellow")
    header_text.append(" | ", style="dim")
    header_text.append(f"Sessions: ", style="white")
    header_text.append(f"{overall.total_sessions:,}", style="bold yellow")
    header_text.append("\n")
    header_text.append("Note: Claude Code keeps ~30 days of history (rolling window)", style="dim italic")

    return Panel(header_text, border_style="cyan")


def _create_activity_graph(daily_stats: dict[str, DailyStats]) -> Panel:
    """
    Create the GitHub-style activity heatmap showing full year.

    Args:
        daily_stats: Dictionary of daily statistics

    Returns:
        Rich Panel containing the activity graph
    """
    # Always show full year: Jan 1 to Dec 31 of current year
    today = datetime.now().date()
    start_date = datetime(today.year, 1, 1).date()
    end_date = datetime(today.year, 12, 31).date()

    # Calculate max tokens for scaling
    max_tokens = max(
        (stats.total_tokens for stats in daily_stats.values()), default=1
    ) if daily_stats else 1

    # Build weeks structure
    # GitHub starts weeks on Sunday, so calculate which day of week Jan 1 is
    # weekday() returns 0=Monday, 6=Sunday
    # We want 0=Sunday, 6=Saturday
    jan1_day = (start_date.weekday() + 1) % 7  # Convert to Sunday=0

    weeks: list[list[tuple[Optional[DailyStats], Optional[datetime.date]]]] = []
    current_week: list[tuple[Optional[DailyStats], Optional[datetime.date]]] = []

    # Pad the first week with None entries before Jan 1
    for i in range(jan1_day):
        # Use None for padding - we'll handle this specially in rendering
        current_week.append((None, None))

    # Now add all days from Jan 1 to Dec 31
    current_date = start_date
    while current_date <= end_date:
        date_key = current_date.strftime("%Y-%m-%d")
        day_stats = daily_stats.get(date_key)
        current_week.append((day_stats, current_date))

        # If we've completed a week (Sunday-Saturday), start a new one
        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []

        current_date += timedelta(days=1)

    # Add any remaining days and pad the final week
    if current_week:
        while len(current_week) < 7:
            # Pad with None for dates after Dec 31
            current_week.append((None, None))
        weeks.append(current_week)

    # Create month labels for the top row
    month_labels = _create_month_labels_github_style(weeks)

    # Create table for graph with equal spacing between columns
    # Use width=4 for better spacing and readability
    table = Table.grid(padding=(0, 0))
    table.add_column(justify="right", style=CLAUDE_TEXT_SECONDARY, width=5)  # Day labels

    for _ in range(len(weeks)):
        table.add_column(justify="center", width=4)  # Wider columns for better spacing

    # Add month labels row at the top with Claude secondary color
    month_labels_styled = [Text(label, style=CLAUDE_TEXT_SECONDARY) for label in month_labels]
    table.add_row("", *month_labels_styled)

    # Show all day labels for clarity with Claude secondary color
    day_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    # Render each day of week as a row (Sunday=0 to Saturday=6)
    for day_idx in range(7):
        row = [Text(day_labels[day_idx], style=CLAUDE_TEXT_SECONDARY)]

        for week in weeks:
            if day_idx < len(week):
                day_stats, date = week[day_idx]
                cell = _get_intensity_cell(day_stats, max_tokens, date)
            else:
                # Shouldn't happen, but handle it anyway
                cell = Text(" ", style="dim")
            row.append(cell)

        table.add_row(*row)

    # Create legend with dot sizes (skip the first one which is empty space)
    legend = Text()
    legend.append("Less ", style=CLAUDE_TEXT_SECONDARY)
    # Show all dot sizes from smallest to largest (skip index 0 which is empty space)
    for i, dot in enumerate(DOT_SIZES[1:], start=1):
        # Map to intensity range
        intensity = 0.3 + ((i - 1) / (len(DOT_SIZES) - 2)) * 0.7
        r = int(CLAUDE_ORANGE_RGB[0] * intensity)
        g = int(CLAUDE_ORANGE_RGB[1] * intensity)
        b = int(CLAUDE_ORANGE_RGB[2] * intensity)
        legend.append(dot, style=f"rgb({r},{g},{b})")
        legend.append(" ", style="dim")
    legend.append(" More", style=CLAUDE_TEXT_SECONDARY)

    # Add contribution count
    total_days = len([d for w in weeks for d, _ in w if d is not None])
    contrib_text = Text()
    contrib_text.append(f"{total_days} days with activity in {today.year}", style="dim")

    return Panel(
        Group(table, Text(""), legend, Text(""), contrib_text),
        title=f"Activity in {today.year}",
        border_style="blue",
        expand=False,  # Don't expand to full terminal width
        width=None,  # Let content determine width
    )


def _create_month_labels_github_style(
    weeks: list[list[tuple[Optional[DailyStats], Optional[datetime.date]]]]
) -> list[str]:
    """
    Create month labels for the X-axis in GitHub style.

    Shows month name at the start of each month that appears in the graph.

    Args:
        weeks: List of weeks (each week is a list of day tuples)

    Returns:
        List of strings for month labels (one per week column)
    """
    labels: list[str] = []
    last_month = None

    for week_idx, week in enumerate(weeks):
        # Get the first valid date in this week
        week_start_month = None
        month_name = ""
        for day_stats, date in week:
            if date is not None:
                week_start_month = date.month
                month_name = date.strftime("%b")
                break

        # Show month label when month changes, with proper width for new column size
        if week_start_month and week_start_month != last_month:
            # Center month abbreviation in 4-char width
            labels.append(f"{month_name:^4}")
            last_month = week_start_month
        else:
            labels.append("    ")

    return labels


def _create_month_labels(
    weeks: list[list[tuple[Optional[DailyStats], datetime.date]]],
    week_dates: list[datetime.date]
) -> list[Text]:
    """
    Create month labels for the X-axis of the activity graph.

    Args:
        weeks: List of weeks (each week is a list of day tuples)
        week_dates: List of dates for the first day of each week

    Returns:
        List of Text objects for month labels (one per week column)
    """
    labels: list[Text] = []
    last_month = None

    for week_idx, week_start in enumerate(week_dates):
        current_month = week_start.strftime("%b")

        # Show month label on first week or when month changes
        if last_month != current_month and week_idx < len(weeks):
            labels.append(Text(current_month[:3], style="dim"))
            last_month = current_month
        else:
            labels.append(Text("  ", style="dim"))

    return labels


def _create_timeline_view(daily_stats: dict[str, DailyStats]) -> Panel:
    """
    Create a detailed timeline view showing daily activity with bar chart.

    Args:
        daily_stats: Dictionary of daily statistics

    Returns:
        Rich Panel containing timeline visualization
    """
    if not daily_stats:
        return Panel(Text("No activity data", style="dim"), title="Daily Timeline", border_style="yellow")

    # Get sorted dates
    dates = sorted(daily_stats.keys())

    # Calculate max for scaling
    max_prompts = max((stats.total_prompts for stats in daily_stats.values()), default=1)
    max_tokens = max((stats.total_tokens for stats in daily_stats.values()), default=1)

    # Create table
    table = Table(title="Daily Activity Timeline", border_style="yellow", show_header=True)
    table.add_column("Date", style="cyan", justify="left", width=12)
    table.add_column("Prompts", style="magenta", justify="right", width=8)
    table.add_column("Activity", style="green", justify="left", width=40)
    table.add_column("Tokens", style="yellow", justify="right", width=15)

    # Show last 15 days with activity
    recent_dates = dates[-15:]

    for date in recent_dates:
        stats = daily_stats[date]

        # Format date
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        date_str = date_obj.strftime("%b %d")

        # Create bar for prompts
        bar_width = int((stats.total_prompts / max_prompts) * 30)
        bar = "█" * bar_width

        # Format tokens (abbreviated)
        if stats.total_tokens >= 1_000_000:
            tokens_str = f"{stats.total_tokens / 1_000_000:.1f}M"
        elif stats.total_tokens >= 1_000:
            tokens_str = f"{stats.total_tokens / 1_000:.1f}K"
        else:
            tokens_str = str(stats.total_tokens)

        table.add_row(
            date_str,
            f"{stats.total_prompts:,}",
            bar,
            tokens_str,
        )

    return Panel(table, border_style="yellow")


def _get_intensity_cell(
    day_stats: Optional[DailyStats], max_tokens: int, date: Optional[datetime.date]
) -> Text:
    """
    Get the colored cell for a specific day based on token usage.
    Uses different-sized dots for terminal, gradient for export.

    Args:
        day_stats: Statistics for the day (None if no activity)
        max_tokens: Maximum tokens in any day (for scaling)
        date: The date of this cell (None for padding)

    Returns:
        Rich Text object with appropriate color and symbol
    """
    if date is None:
        # Padding cell
        return Text(" ", style="dim")

    today = datetime.now().date()

    # Future days: empty space
    if date > today:
        return Text(" ")

    # Past days with no activity: empty space
    if not day_stats or day_stats.total_tokens == 0:
        return Text(" ")

    # Calculate intensity ratio (0.0 to 1.0)
    ratio = day_stats.total_tokens / max_tokens if max_tokens > 0 else 0

    # Apply non-linear scaling to make differences more visible
    # Using square root makes lower values more distinguishable
    ratio = ratio ** 0.5

    # Choose dot size based on activity level (1-4, since 0 is empty space)
    if ratio >= 0.8:
        dot_idx = 4  # Largest (⬤)
    elif ratio >= 0.6:
        dot_idx = 3  # Large (●)
    elif ratio >= 0.4:
        dot_idx = 2  # Medium (•)
    else:
        dot_idx = 1  # Small (·) - for any activity > 0

    dot = DOT_SIZES[dot_idx]

    # Calculate color intensity
    base_r, base_g, base_b = CLAUDE_ORANGE_RGB
    min_intensity = 0.3
    intensity = min_intensity + (ratio * (1.0 - min_intensity))

    r = int(base_r * intensity)
    g = int(base_g * intensity)
    b = int(base_b * intensity)

    return Text(dot, style=f"rgb({r},{g},{b})")


def _create_stats_table(overall: DailyStats) -> Table:
    """
    Create table with detailed token statistics.

    Args:
        overall: Overall statistics

    Returns:
        Rich Table with token breakdown
    """
    table = Table(title="Token Usage Breakdown", border_style="green")

    table.add_column("Metric", style="cyan", justify="left")
    table.add_column("Count", style="yellow", justify="right")
    table.add_column("Percentage", style="magenta", justify="right")

    total = overall.total_tokens if overall.total_tokens > 0 else 1

    table.add_row(
        "Input Tokens",
        f"{overall.input_tokens:,}",
        f"{(overall.input_tokens / total * 100):.1f}%",
    )
    table.add_row(
        "Output Tokens",
        f"{overall.output_tokens:,}",
        f"{(overall.output_tokens / total * 100):.1f}%",
    )
    table.add_row(
        "Cache Creation",
        f"{overall.cache_creation_tokens:,}",
        f"{(overall.cache_creation_tokens / total * 100):.1f}%",
    )
    table.add_row(
        "Cache Read",
        f"{overall.cache_read_tokens:,}",
        f"{(overall.cache_read_tokens / total * 100):.1f}%",
    )
    table.add_row(
        "Total",
        f"{overall.total_tokens:,}",
        "100.0%",
        style="bold",
    )

    return table


def _create_breakdown_tables(overall: DailyStats) -> Group:
    """
    Create tables showing breakdown by model and folder.

    Args:
        overall: Overall statistics

    Returns:
        Rich Group containing breakdown tables
    """
    # Models table
    models_table = Table(title="Models Used", border_style="blue")
    models_table.add_column("Model", style="cyan")
    for model in sorted(overall.models):
        # Shorten long model names for display (model names use / not paths)
        display_name = model.split("/")[-1] if "/" in model else model
        models_table.add_row(display_name)

    # Folders table
    folders_table = Table(title="Project Folders", border_style="yellow")
    folders_table.add_column("Folder", style="cyan")
    for folder in sorted(overall.folders):
        # Show only last 2 parts of path for brevity (cross-platform)
        display_name = _shorten_path(folder)
        folders_table.add_row(display_name)

    # Create side-by-side layout using Table.grid
    layout = Table.grid(padding=(0, 2))
    layout.add_column()
    layout.add_column()
    layout.add_row(models_table, folders_table)

    return Group(layout)
#endregion
