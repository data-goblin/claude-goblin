#region Imports
from collections import defaultdict
from datetime import datetime

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.aggregation.daily_stats import AggregatedStats
from src.models.usage_record import UsageRecord

#endregion


#region Constants
# Claude-inspired color scheme
ORANGE = "#ff8800"
CYAN = "cyan"
DIM = "grey50"
BAR_WIDTH = 20
#endregion


#region Functions


def _format_number(num: int) -> str:
    """
    Format number with thousands separator and appropriate suffix.

    Args:
        num: Number to format

    Returns:
        Formatted string (e.g., "1.4bn", "523.7M", "45.2K", "1.234")
    """
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}bn".replace(".", ".")
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M".replace(".", ".")
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K".replace(".", ".")
    else:
        # Add thousands separator for numbers < 1000
        return f"{num:,}".replace(",", ".")


def _create_bar(value: int, max_value: int, width: int = BAR_WIDTH, color: str = ORANGE) -> Text:
    """
    Create a simple text bar for visualization.

    Args:
        value: Current value
        max_value: Maximum value for scaling
        width: Width of bar in characters
        color: Color for the filled portion of the bar

    Returns:
        Rich Text object with colored bar
    """
    if max_value == 0:
        return Text("░" * width, style=DIM)

    filled = int((value / max_value) * width)
    bar = Text()
    bar.append("█" * filled, style=color)
    bar.append("░" * (width - filled), style=DIM)
    return bar


def render_dashboard(stats: AggregatedStats, records: list[UsageRecord], console: Console, skip_limits: bool = False, clear_screen: bool = True, date_range: str = None, limits_from_db: dict | None = None, fast_mode: bool = False) -> None:
    """
    Render a concise, modern dashboard with KPI cards and breakdowns.

    Args:
        stats: Aggregated statistics
        records: Raw usage records for detailed breakdowns
        console: Rich console for rendering
        skip_limits: If True, skip fetching current limits for faster display
        clear_screen: If True, clear the screen before rendering (default True)
        date_range: Optional date range string to display in footer
        limits_from_db: Pre-fetched limits from database (avoids live fetch)
        fast_mode: If True, show warning that data is from last update
    """
    if clear_screen:
        console.clear()

    # Use simple text layout for narrow terminals (< 90 cols)
    if console.width < 90:
        _render_simple_dashboard(stats, records, console, date_range, fast_mode)
        return

    # Create KPI cards with limits (shows spinner if loading limits)
    kpi_section = _create_kpi_section(stats.overall_totals, skip_limits=skip_limits, console=console, limits_from_db=limits_from_db)

    # Create breakdowns
    model_breakdown = _create_model_breakdown(records)
    project_breakdown = _create_project_breakdown(records)

    # Create footer with export info and date range
    footer = _create_footer(date_range, fast_mode=fast_mode)

    # Render all components
    console.print(kpi_section, end="")
    console.print()  # Blank line between sections
    console.print(model_breakdown, end="")
    console.print()  # Blank line between sections
    console.print(project_breakdown, end="")
    console.print()  # Blank line before footer
    console.print(footer)


def _render_simple_dashboard(stats: AggregatedStats, records: list[UsageRecord], console: Console, date_range: str = None, fast_mode: bool = False) -> None:
    """
    Render a simple text-based dashboard for narrow terminals.

    Args:
        stats: Aggregated statistics
        records: Raw usage records
        console: Rich console
        date_range: Optional date range
        fast_mode: If True, show fast mode warning
    """
    overall = stats.overall_totals

    # Header
    console.print(f"\n[bold {ORANGE}]CLAUDE USAGE[/bold {ORANGE}]\n")

    # KPIs as simple lines
    console.print(f"  Tokens:   [bold {ORANGE}]{_format_number(overall.total_tokens)}[/bold {ORANGE}]")
    console.print(f"  Prompts:  [bold white]{_format_number(overall.total_prompts)}[/bold white]")
    console.print(f"  Sessions: [bold white]{_format_number(overall.total_sessions)}[/bold white]")
    console.print()

    # Model breakdown
    model_tokens: dict[str, int] = {}
    for record in records:
        if record.model and record.token_usage and record.model != "<synthetic>":
            model_tokens[record.model] = model_tokens.get(record.model, 0) + record.token_usage.total_tokens

    if model_tokens:
        console.print("[bold]Models:[/bold]")
        total = sum(model_tokens.values())
        for model, tokens in sorted(model_tokens.items(), key=lambda x: x[1], reverse=True)[:5]:
            name = model.replace("claude-", "")
            pct = (tokens / total * 100) if total > 0 else 0
            console.print(f"  {name[:25]:<25} [{ORANGE}]{_format_number(tokens):>8}[/{ORANGE}] [{CYAN}]{pct:5.1f}%[/{CYAN}]")
        console.print()

    # Project breakdown
    folder_tokens: dict[str, int] = {}
    for record in records:
        if record.token_usage:
            folder_tokens[record.folder] = folder_tokens.get(record.folder, 0) + record.token_usage.total_tokens

    if folder_tokens:
        console.print("[bold]Projects:[/bold]")
        total = sum(folder_tokens.values())
        for folder, tokens in sorted(folder_tokens.items(), key=lambda x: x[1], reverse=True)[:5]:
            parts = folder.split("/")
            name = "/".join(parts[-2:]) if len(parts) > 2 else folder
            name = name[:25]
            pct = (tokens / total * 100) if total > 0 else 0
            console.print(f"  {name:<25} [{ORANGE}]{_format_number(tokens):>8}[/{ORANGE}] [{CYAN}]{pct:5.1f}%[/{CYAN}]")
        console.print()

    # Footer
    if fast_mode:
        console.print("[bold red]Fast mode: data from cache[/bold red]")
    if date_range:
        console.print(f"[{DIM}]Data: {date_range}[/{DIM}]")
    console.print(f"[{DIM}]Tip: ccg export --open for heatmap[/{DIM}]")


def _create_kpi_section(overall, skip_limits: bool = False, console: Console = None, limits_from_db: dict | None = None) -> Group:
    """
    Create KPI cards with individual limit boxes beneath each.

    Args:
        overall: Overall statistics
        skip_limits: If True, skip fetching current limits (faster)
        console: Console instance for showing spinner
        limits_from_db: Pre-fetched limits from database (avoids live fetch)

    Returns:
        Group containing KPI cards and limit boxes
    """
    # Use limits from DB if provided, otherwise fetch live (unless skipped)
    limits = limits_from_db
    if limits is None and not skip_limits:
        from src.commands.limits import capture_limits
        if console:
            with console.status(f"[bold {ORANGE}]Loading usage limits...", spinner="dots", spinner_style=ORANGE):
                limits = capture_limits()
        else:
            limits = capture_limits()

    # Create KPI cards
    kpi_grid = Table.grid(padding=(0, 2), expand=False)
    kpi_grid.add_column(justify="center")
    kpi_grid.add_column(justify="center")
    kpi_grid.add_column(justify="center")

    # Total Tokens card
    tokens_card = Panel(
        Text(_format_number(overall.total_tokens), style=f"bold {ORANGE}"),
        title="Total Tokens",
        border_style="white",
        width=28,
    )

    # Total Prompts card
    prompts_card = Panel(
        Text(_format_number(overall.total_prompts), style="bold white"),
        title="Prompts Sent",
        border_style="white",
        width=28,
    )

    # Total Sessions card
    sessions_card = Panel(
        Text(_format_number(overall.total_sessions), style="bold white"),
        title="Active Sessions",
        border_style="white",
        width=28,
    )

    kpi_grid.add_row(tokens_card, prompts_card, sessions_card)

    # Create individual limit boxes if available
    if limits and "error" not in limits:
        limit_grid = Table.grid(padding=(0, 2), expand=False)
        limit_grid.add_column(justify="center")
        limit_grid.add_column(justify="center")
        limit_grid.add_column(justify="center")

        # Remove timezone info from reset dates
        session_reset = limits['session_reset'].split(' (')[0] if '(' in limits['session_reset'] else limits['session_reset']
        week_reset = limits['week_reset'].split(' (')[0] if '(' in limits['week_reset'] else limits['week_reset']
        opus_reset = limits['opus_reset'].split(' (')[0] if '(' in limits['opus_reset'] else limits['opus_reset']

        # Session limit box
        session_bar = _create_bar(limits["session_pct"], 100, width=16, color="red")
        session_content = Text()
        session_content.append(f"{limits['session_pct']}% ", style="bold red")
        session_content.append(session_bar)
        session_content.append(f"\nResets: {session_reset}", style="white")
        session_box = Panel(
            session_content,
            title="[red]Session Limit",
            border_style="white",
            width=28,
        )

        # Week limit box
        week_bar = _create_bar(limits["week_pct"], 100, width=16, color="red")
        week_content = Text()
        week_content.append(f"{limits['week_pct']}% ", style="bold red")
        week_content.append(week_bar)
        week_content.append(f"\nResets: {week_reset}", style="white")
        week_box = Panel(
            week_content,
            title="[red]Weekly Limit",
            border_style="white",
            width=28,
        )

        # Opus limit box
        opus_bar = _create_bar(limits["opus_pct"], 100, width=16, color="red")
        opus_content = Text()
        opus_content.append(f"{limits['opus_pct']}% ", style="bold red")
        opus_content.append(opus_bar)
        opus_content.append(f"\nResets: {opus_reset}", style="white")
        opus_box = Panel(
            opus_content,
            title="[red]Opus Limit",
            border_style="white",
            width=28,
        )

        limit_grid.add_row(session_box, week_box, opus_box)

        # Add spacing between KPI cards and limits with a simple newline
        spacing = Text("\n")
        return Group(kpi_grid, spacing, limit_grid)
    else:
        return Group(kpi_grid)


def _create_kpi_cards(overall) -> Table:
    """
    Create 3 KPI cards showing key metrics.

    Args:
        overall: Overall statistics

    Returns:
        Table grid with KPI cards
    """
    grid = Table.grid(padding=(0, 2), expand=False)
    grid.add_column(justify="center")
    grid.add_column(justify="center")
    grid.add_column(justify="center")

    # Total Tokens card
    tokens_card = Panel(
        Text.assemble(
            (_format_number(overall.total_tokens), f"bold {ORANGE}"),
            "\n",
            ("Total Tokens", DIM),
        ),
        border_style="white",
        width=28,
    )

    # Total Prompts card
    prompts_card = Panel(
        Text.assemble(
            (_format_number(overall.total_prompts), f"bold {ORANGE}"),
            "\n",
            ("Prompts Sent", DIM),
        ),
        border_style="white",
        width=28,
    )

    # Total Sessions card
    sessions_card = Panel(
        Text.assemble(
            (_format_number(overall.total_sessions), f"bold {ORANGE}"),
            "\n",
            ("Active Sessions", DIM),
        ),
        border_style="white",
        width=28,
    )

    grid.add_row(tokens_card, prompts_card, sessions_card)
    return grid


def _create_limits_bars() -> Panel | None:
    """
    Create progress bars showing current usage limits.

    Returns:
        Panel with limit progress bars, or None if no limits data
    """
    # Try to capture current limits
    from src.commands.limits import capture_limits

    limits = capture_limits()
    if not limits or "error" in limits:
        return None

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="white", justify="left")
    table.add_column("Bar", justify="left")
    table.add_column("Percent", style=ORANGE, justify="right")
    table.add_column("Reset", style=CYAN, justify="left")

    # Session limit
    session_bar = _create_bar(limits["session_pct"], 100, width=30)
    table.add_row(
        "[bold]Session",
        session_bar,
        f"{limits['session_pct']}%",
        f"resets {limits['session_reset']}",
    )

    # Week limit
    week_bar = _create_bar(limits["week_pct"], 100, width=30)
    table.add_row(
        "[bold]Week",
        week_bar,
        f"{limits['week_pct']}%",
        f"resets {limits['week_reset']}",
    )

    # Opus limit
    opus_bar = _create_bar(limits["opus_pct"], 100, width=30)
    table.add_row(
        "[bold]Opus",
        opus_bar,
        f"{limits['opus_pct']}%",
        f"resets {limits['opus_reset']}",
    )

    return Panel(
        table,
        title="[bold]Usage Limits",
        border_style="white",
    )


def _create_model_breakdown(records: list[UsageRecord]) -> Panel:
    """
    Create table showing token usage per model.

    Args:
        records: List of usage records

    Returns:
        Panel with model breakdown table
    """
    # Aggregate tokens by model
    model_tokens: dict[str, int] = defaultdict(int)

    for record in records:
        if record.model and record.token_usage and record.model != "<synthetic>":
            model_tokens[record.model] += record.token_usage.total_tokens

    if not model_tokens:
        return Panel(
            Text("No model data available", style=DIM),
            title="[bold]Tokens by Model",
            border_style="white",
        )

    # Calculate total and max
    total_tokens = sum(model_tokens.values())
    max_tokens = max(model_tokens.values())

    # Sort by usage
    sorted_models = sorted(model_tokens.items(), key=lambda x: x[1], reverse=True)

    # Create table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Model", style="white", justify="left", width=25)
    table.add_column("Bar", justify="left")
    table.add_column("Tokens", style=ORANGE, justify="right")
    table.add_column("Percentage", style=CYAN, justify="right")

    for model, tokens in sorted_models:
        # Shorten model name
        display_name = model.split("/")[-1] if "/" in model else model
        if "claude" in display_name.lower():
            display_name = display_name.replace("claude-", "")

        percentage = (tokens / total_tokens * 100) if total_tokens > 0 else 0

        # Create bar
        bar = _create_bar(tokens, max_tokens, width=20)

        table.add_row(
            display_name,
            bar,
            _format_number(tokens),
            f"{percentage:.1f}%",
        )

    return Panel(
        table,
        title="[bold]Tokens by Model",
        border_style="white",
    )


def _create_project_breakdown(records: list[UsageRecord]) -> Panel:
    """
    Create table showing token usage per project.

    Args:
        records: List of usage records

    Returns:
        Panel with project breakdown table
    """
    # Aggregate tokens by folder
    folder_tokens: dict[str, int] = defaultdict(int)

    for record in records:
        if record.token_usage:
            folder_tokens[record.folder] += record.token_usage.total_tokens

    if not folder_tokens:
        return Panel(
            Text("No project data available", style=DIM),
            title="[bold]Tokens by Project",
            border_style="white",
        )

    # Calculate total and max
    total_tokens = sum(folder_tokens.values())

    # Sort by usage
    sorted_folders = sorted(folder_tokens.items(), key=lambda x: x[1], reverse=True)

    # Limit to top 10 projects
    sorted_folders = sorted_folders[:10]
    max_tokens = max(tokens for _, tokens in sorted_folders)

    # Create table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Project", style="white", justify="left", overflow="crop")
    table.add_column("Bar", justify="left", overflow="crop")
    table.add_column("Tokens", style=ORANGE, justify="right")
    table.add_column("Percentage", style=CYAN, justify="right")

    for folder, tokens in sorted_folders:
        # Show only last 2-3 parts of path and truncate if needed
        parts = folder.split("/")
        if len(parts) > 3:
            display_name = ".../" + "/".join(parts[-2:])
        elif len(parts) > 2:
            display_name = "/".join(parts[-2:])
        else:
            display_name = folder

        # Manually truncate to 35 chars without ellipses
        if len(display_name) > 35:
            display_name = display_name[:35]

        percentage = (tokens / total_tokens * 100) if total_tokens > 0 else 0

        # Create bar
        bar = _create_bar(tokens, max_tokens, width=20)

        table.add_row(
            display_name,
            bar,
            _format_number(tokens),
            f"{percentage:.1f}%",
        )

    return Panel(
        table,
        title="[bold]Tokens by Project",
        border_style="white",
    )


def _create_footer(date_range: str = None, fast_mode: bool = False) -> Text:
    """
    Create footer with export command info and date range.

    Args:
        date_range: Optional date range string to display
        fast_mode: If True, show warning about fast mode

    Returns:
        Text with export instructions and date range
    """
    footer = Text()

    # Add fast mode warning if enabled
    if fast_mode:
        from src.storage.snapshot_db import get_database_stats
        db_stats = get_database_stats()
        if db_stats.get("newest_timestamp"):
            # Format ISO timestamp to be more readable
            timestamp_str = db_stats["newest_timestamp"]
            try:
                dt = datetime.fromisoformat(timestamp_str)
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                footer.append("⚠ Fast mode: Reading from last update (", style="bold red")
                footer.append(f"{formatted_time}", style="bold red")
                footer.append(")\n\n", style="bold red")
            except (ValueError, AttributeError):
                footer.append(f"⚠ Fast mode: Reading from last update ({timestamp_str})\n\n", style="bold red")
        else:
            footer.append("⚠ Fast mode: Reading from database (no timestamp available)\n\n", style="bold red")

    # Add date range if provided
    if date_range:
        footer.append("Data range: ", style=DIM)
        footer.append(f"{date_range}\n", style=f"bold {CYAN}")

    # Add export tip
    footer.append("Tip: ", style=DIM)
    footer.append("View yearly heatmap with ", style=DIM)
    footer.append("ccg export --open", style=f"bold {CYAN}")

    return footer


#endregion
