#region Imports
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns

from src.aggregation.daily_stats import AggregatedStats
from src.models.usage_record import UsageRecord
#endregion


#region Constants
# ═══════════════════════════════════════════════════════════════════════════════
# AESTHETIC: "Warm Data Observatory"
# A terminal dashboard that feels like a cozy mission control center.
# Warm orange gradients, clean box-drawing, personality through stats.
# ═══════════════════════════════════════════════════════════════════════════════

# Color Palette - Warm orange spectrum with cool accents
AMBER_GLOW = "#ffaa00"      # Primary accent - warm amber
EMBER = "#ff6600"           # Hot accent - for emphasis
SUNSET = "#cc5500"          # Mid-tone orange
CLAY = "#994400"            # Darker orange
RUST = "#663300"            # Darkest orange
SAGE = "#88aa77"            # Cool complement - for secondary data
SLATE = "#667788"           # Cool neutral
CHARCOAL = "#333340"        # Dark background tone
DIM = "#555566"             # Muted text
GHOST = "#444455"           # Very muted

# Bar characters - smooth gradient
BAR_CHARS = "▏▎▍▌▋▊▉█"

# Heatmap intensity - geometric progression for visual pop
HEAT_EMPTY = "·"
HEAT_LEVELS = ["░", "▒", "▓", "█"]
HEAT_COLORS = ["#442200", "#774400", "#aa6600", AMBER_GLOW]

# Box drawing for panels
BOX_H = "─"
BOX_V = "│"
BOX_TL = "╭"
BOX_TR = "╮"
BOX_BL = "╰"
BOX_BR = "╯"
#endregion


#region Helper Functions
def _parse_path_parts(path_str: str) -> list[str]:
    """Parse path into parts, handling both Unix and Windows separators.

    Paths from Claude Code JSONL files may contain either / or \\ depending
    on the platform where the data was generated.
    """
    # Try to detect path type by looking for Windows drive letters or backslashes
    if "\\" in path_str or (len(path_str) > 1 and path_str[1] == ":"):
        return list(PureWindowsPath(path_str).parts)
    else:
        return list(PurePosixPath(path_str).parts)


def _shorten_path(path_str: str, max_parts: int = 2) -> str:
    """Shorten a path to show only the last N parts, cross-platform."""
    parts = _parse_path_parts(path_str)
    if len(parts) > max_parts:
        return "…/" + "/".join(parts[-max_parts:])
    return path_str


def _fmt(num: int) -> str:
    """Format number with K/M/B suffix."""
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)


def _gradient_bar(value: int, max_value: int, width: int = 20) -> Text:
    """Create a smooth gradient bar using block characters."""
    # Guard against invalid width
    if width <= 0:
        return Text()
    if max_value == 0:
        return Text("·" * width, style=GHOST)

    ratio = min(1.0, value / max_value)
    filled_width = ratio * width
    full_blocks = int(filled_width)
    partial = filled_width - full_blocks

    bar = Text()

    # Full blocks with gradient color based on position
    for i in range(full_blocks):
        pos_ratio = i / width  # Safe: width > 0 guaranteed above
        if pos_ratio < 0.3:
            color = RUST
        elif pos_ratio < 0.6:
            color = SUNSET
        elif pos_ratio < 0.85:
            color = EMBER
        else:
            color = AMBER_GLOW
        bar.append("█", style=color)

    # Partial block
    if partial > 0 and full_blocks < width:
        char_idx = max(0, min(int(partial * len(BAR_CHARS)), len(BAR_CHARS) - 1))
        bar.append(BAR_CHARS[char_idx], style=SUNSET)
        full_blocks += 1

    # Empty space
    remaining = width - full_blocks
    if remaining > 0:
        bar.append("·" * remaining, style=GHOST)

    return bar


def _duration_str(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds >= 86400:
        d = int(seconds // 86400)
        h = int((seconds % 86400) // 3600)
        return f"{d}d {h}h"
    elif seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"
    else:
        m = int(seconds // 60)
        return f"{m}m"
#endregion


#region Dashboard Components
def _create_header(stats: AggregatedStats, records: list[UsageRecord]) -> Text:
    """Create a distinctive header with key stats."""
    header = Text()

    # Title with warm glow
    header.append("  ◆ ", style=EMBER)
    header.append("CLAUDE USAGE", style=f"bold {AMBER_GLOW}")
    header.append(" ◆\n\n", style=EMBER)

    # Key metrics in a horizontal layout
    total = stats.overall_totals

    header.append("    ", style=DIM)
    header.append(_fmt(total.total_tokens), style=f"bold {AMBER_GLOW}")
    header.append(" tokens", style=DIM)
    header.append("  │  ", style=GHOST)
    header.append(str(total.total_prompts), style="bold white")
    header.append(" prompts", style=DIM)
    header.append("  │  ", style=GHOST)
    header.append(str(total.total_sessions), style="bold white")
    header.append(" sessions\n", style=DIM)

    return header


def _create_heatmap(records: list[UsageRecord]) -> Panel:
    """
    Create a GitHub-style activity heatmap with personality.
    The visual centerpiece of the dashboard.
    """
    if not records:
        return Panel(
            Text("No activity data yet", style=DIM),
            title="[bold]Activity",
            border_style=GHOST,
        )

    # Aggregate data
    daily_tokens: dict[str, int] = defaultdict(int)
    daily_sessions: dict[str, set] = defaultdict(set)
    model_tokens: dict[str, int] = defaultdict(int)
    hourly_activity: dict[int, int] = defaultdict(int)

    for record in records:
        date_key = record.date_key
        if record.token_usage:
            daily_tokens[date_key] += record.token_usage.total_tokens
            if record.model:
                model_tokens[record.model] += record.token_usage.total_tokens
        daily_sessions[date_key].add(record.session_id)
        hourly_activity[record.timestamp.hour] += 1

    if not daily_tokens:
        return Panel(Text("No token data", style=DIM), border_style=GHOST)

    today = datetime.now().date()
    sorted_dates = sorted(daily_tokens.keys())
    oldest_date = datetime.strptime(sorted_dates[0], "%Y-%m-%d").date()
    days_of_data = (today - oldest_date).days + 1
    max_tokens = max(daily_tokens.values())

    # Build weeks (show ~20 weeks for compact view)
    num_weeks = min(20, (days_of_data // 7) + 2)
    start_date = today - timedelta(days=num_weeks * 7)
    start_date -= timedelta(days=(start_date.weekday() + 1) % 7)  # Start on Sunday

    weeks: list[list[tuple[str, int]]] = []
    current_week: list[tuple[str, int]] = []
    current_date = start_date

    while current_date <= today:
        date_key = current_date.strftime("%Y-%m-%d")
        tokens = daily_tokens.get(date_key, 0)
        current_week.append((date_key, tokens))
        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []
        current_date += timedelta(days=1)
    if current_week:
        weeks.append(current_week)

    # Build heatmap text
    content = Text()

    # Month labels
    content.append("       ", style=DIM)
    prev_month = None
    for week in weeks:
        if week:
            dt = datetime.strptime(week[0][0], "%Y-%m-%d")
            month = dt.strftime("%b")
            if month != prev_month:
                content.append(f"{month[:3]:<4}", style=DIM)
                prev_month = month
            else:
                content.append("    ", style=DIM)
    content.append("\n")

    # Day rows
    day_labels = ["", "Mon", "", "Wed", "", "Fri", ""]
    for day_idx in range(7):
        content.append(f"  {day_labels[day_idx]:>3} ", style=DIM)
        for week in weeks:
            if day_idx < len(week):
                date_key, tokens = week[day_idx]
                dt = datetime.strptime(date_key, "%Y-%m-%d").date()

                if dt > today:
                    content.append(" ", style=DIM)
                elif tokens == 0:
                    content.append(HEAT_EMPTY, style=GHOST)
                else:
                    ratio = (tokens / max_tokens) ** 0.5  # sqrt scaling
                    level = min(3, int(ratio * 4))
                    content.append(HEAT_LEVELS[level], style=HEAT_COLORS[level])
            else:
                content.append(" ")
        content.append("\n")

    # Legend
    content.append("\n       Less ", style=DIM)
    content.append(HEAT_EMPTY + " ", style=GHOST)
    for i, char in enumerate(HEAT_LEVELS):
        content.append(char + " ", style=HEAT_COLORS[i])
    content.append("More\n", style=DIM)

    # Fun stats section
    content.append("\n")

    # Calculate stats
    total_tokens = sum(daily_tokens.values())
    total_sessions = sum(len(s) for s in daily_sessions.values())
    active_days = len([d for d in daily_tokens.values() if d > 0])

    # Favorite model
    fav_model = "Unknown"
    if model_tokens:
        fav_model = max(model_tokens.items(), key=lambda x: x[1])[0]
        fav_model = fav_model.replace("claude-", "").split("-20")[0].replace("-", " ").title()

    # Streaks
    current_streak = 0
    check = today
    while check >= oldest_date:
        if daily_tokens.get(check.strftime("%Y-%m-%d"), 0) > 0:
            current_streak += 1
            check -= timedelta(days=1)
        else:
            break

    longest_streak = 0
    temp = 0
    for d in sorted(daily_tokens.keys()):
        if daily_tokens[d] > 0:
            temp += 1
            longest_streak = max(longest_streak, temp)
        else:
            temp = 0

    # Peak hour
    peak_hour = max(hourly_activity.items(), key=lambda x: x[1])[0] if hourly_activity else 12

    # Longest session
    session_times: dict[str, tuple[datetime, datetime]] = {}
    for r in records:
        sid = r.session_id
        if sid not in session_times:
            session_times[sid] = (r.timestamp, r.timestamp)
        else:
            first, last = session_times[sid]
            session_times[sid] = (min(first, r.timestamp), max(last, r.timestamp))

    longest_sec = max(((last - first).total_seconds() for first, last in session_times.values()), default=0)

    # Stats grid - two columns
    content.append("  ╭─────────────────────────────────────────╮\n", style=DIM)

    # Row 1: Favorite model & Total tokens
    content.append("  │ ", style=DIM)
    content.append("★ ", style=EMBER)
    content.append(f"{fav_model:<16}", style=f"bold {AMBER_GLOW}")
    content.append("  ", style=DIM)
    content.append(f"{_fmt(total_tokens):>10}", style=f"bold {AMBER_GLOW}")
    content.append(" tokens", style=DIM)
    content.append(" │\n", style=DIM)

    # Row 2: Current streak & Longest streak
    content.append("  │ ", style=DIM)
    content.append("🔥", style=EMBER)
    content.append(f" {current_streak} day streak        ", style="white")
    content.append(f"Best: {longest_streak} days", style=DIM)
    content.append("  │\n", style=DIM)

    # Row 3: Sessions & Peak hour
    content.append("  │ ", style=DIM)
    content.append(f"  {total_sessions} sessions", style="white")
    content.append(f"           Peak: {peak_hour:02d}:00-{(peak_hour+1)%24:02d}:00", style=DIM)
    content.append(" │\n", style=DIM)

    # Row 4: Longest session & Active days
    content.append("  │ ", style=DIM)
    content.append(f"  Longest: {_duration_str(longest_sec):<8}", style="white")
    content.append(f"      Active: {active_days}/{days_of_data} days", style=DIM)
    content.append(" │\n", style=DIM)

    content.append("  ╰─────────────────────────────────────────╯\n", style=DIM)

    # Fun comparison
    if longest_sec > 1320:  # > 22 mins
        office_eps = int(longest_sec / 60 / 22)
        if office_eps >= 1:
            content.append(f"\n  💡 Longest session = {office_eps}× The Office episodes\n", style=f"italic {SAGE}")

    return Panel(
        content,
        title=f"[bold {AMBER_GLOW}]◈ Activity Heatmap",
        border_style=SLATE,
        padding=(0, 1),
    )


def _create_model_breakdown(records: list[UsageRecord]) -> Panel:
    """Create a visual breakdown of token usage by model."""
    model_data: dict[str, dict] = defaultdict(lambda: {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "total": 0})

    for record in records:
        if record.model and record.token_usage and record.model != "<synthetic>":
            m = record.model
            model_data[m]["input"] += record.token_usage.input_tokens
            model_data[m]["output"] += record.token_usage.output_tokens
            model_data[m]["cache_write"] += record.token_usage.cache_creation_tokens
            model_data[m]["cache_read"] += record.token_usage.cache_read_tokens
            model_data[m]["total"] += record.token_usage.total_tokens

    if not model_data:
        return Panel(Text("No model data", style=DIM), title="Models", border_style=GHOST)

    total_all = sum(d["total"] for d in model_data.values())
    max_total = max(d["total"] for d in model_data.values())
    sorted_models = sorted(model_data.items(), key=lambda x: x[1]["total"], reverse=True)

    content = Text()

    for model, data in sorted_models[:5]:
        # Clean model name
        name = model.replace("claude-", "").split("-20")[0]
        pct = (data["total"] / total_all * 100) if total_all > 0 else 0

        # Model name and percentage
        content.append(f"  {name:<20}", style="white")
        content.append(f"{pct:5.1f}%\n", style=AMBER_GLOW)

        # Visual bar
        content.append("  ")
        content.append(_gradient_bar(data["total"], max_total, width=26))
        content.append(f" {_fmt(data['total']):>6}\n", style=DIM)

        # Token breakdown (input/output)
        in_pct = (data["input"] / data["total"] * 100) if data["total"] > 0 else 0
        out_pct = (data["output"] / data["total"] * 100) if data["total"] > 0 else 0
        content.append(f"  ", style=DIM)
        content.append(f"in:{in_pct:4.0f}% ", style=SAGE)
        content.append(f"out:{out_pct:4.0f}%", style=SLATE)
        content.append("\n\n", style=DIM)

    return Panel(
        content,
        title=f"[bold {AMBER_GLOW}]◈ Models",
        border_style=SLATE,
        padding=(0, 1),
    )


def _create_branch_breakdown(records: list[UsageRecord]) -> Panel:
    """Create breakdown by git branch."""
    branch_tokens: dict[str, int] = defaultdict(int)

    for record in records:
        if record.token_usage:
            branch = record.git_branch or "detached"
            branch_tokens[branch] += record.token_usage.total_tokens

    if not branch_tokens:
        return Panel(Text("No branch data", style=DIM), title="Branches", border_style=GHOST)

    total = sum(branch_tokens.values())
    sorted_branches = sorted(branch_tokens.items(), key=lambda x: x[1], reverse=True)

    # Limit to top 5 + other
    if len(sorted_branches) > 5:
        top = sorted_branches[:5]
        other = sum(t for _, t in sorted_branches[5:])
        if other > 0:
            top.append(("other", other))
        sorted_branches = top

    max_tokens = max(t for _, t in sorted_branches)

    content = Text()
    for branch, tokens in sorted_branches:
        name = branch[:20] + "…" if len(branch) > 20 else branch
        pct = (tokens / total * 100) if total > 0 else 0

        content.append(f"  {name:<21}", style="white")
        content.append(_gradient_bar(tokens, max_tokens, width=15))
        content.append(f" {pct:5.1f}%\n", style=DIM)

    return Panel(
        content,
        title=f"[bold {AMBER_GLOW}]◈ Branches",
        border_style=SLATE,
        padding=(0, 1),
    )


def _create_project_breakdown(records: list[UsageRecord]) -> Panel:
    """Create breakdown by project folder."""
    folder_tokens: dict[str, int] = defaultdict(int)

    for record in records:
        if record.token_usage:
            folder_tokens[record.folder] += record.token_usage.total_tokens

    if not folder_tokens:
        return Panel(Text("No project data", style=DIM), title="Projects", border_style=GHOST)

    total = sum(folder_tokens.values())
    sorted_folders = sorted(folder_tokens.items(), key=lambda x: x[1], reverse=True)[:8]
    max_tokens = max(t for _, t in sorted_folders)

    content = Text()
    for folder, tokens in sorted_folders:
        # Shorten path (cross-platform)
        name = _shorten_path(folder)
        name = name[:25] + "…" if len(name) > 25 else name

        pct = (tokens / total * 100) if total > 0 else 0

        content.append(f"  {name:<26}", style="white")
        content.append(_gradient_bar(tokens, max_tokens, width=12))
        content.append(f" {pct:5.1f}%\n", style=DIM)

    return Panel(
        content,
        title=f"[bold {AMBER_GLOW}]◈ Projects",
        border_style=SLATE,
        padding=(0, 1),
    )


def _create_footer(date_range: Optional[str] = None, fast_mode: bool = False) -> Text:
    """Create footer with date range and tips."""
    footer = Text()

    if fast_mode:
        from src.storage.snapshot_db import get_database_stats
        db_stats = get_database_stats()
        if db_stats.get("newest_timestamp"):
            try:
                dt = datetime.fromisoformat(db_stats["newest_timestamp"])
                footer.append("  ⚡ Fast mode: ", style=f"bold {EMBER}")
                footer.append(f"data from {dt.strftime('%Y-%m-%d %H:%M')}\n", style=DIM)
            except (ValueError, AttributeError):
                footer.append("  ⚡ Fast mode enabled\n", style=f"bold {EMBER}")

    if date_range:
        footer.append(f"  📅 {date_range}\n", style=DIM)

    footer.append("\n  💡 ", style=DIM)
    footer.append("ccg export --open", style=f"bold {SAGE}")
    footer.append(" for full yearly heatmap", style=DIM)

    return footer
#endregion


#region Main Render Function
def render_dashboard(
    stats: AggregatedStats,
    records: list[UsageRecord],
    console: Console,
    skip_limits: bool = False,  # Kept for API compatibility, currently unused
    clear_screen: bool = True,
    date_range: Optional[str] = None,
    limits_from_db: Optional[dict] = None,  # Kept for API compatibility, currently unused
    fast_mode: bool = False
) -> None:
    """
    Render the complete dashboard with warm, data-observatory aesthetic.

    Note: Limits tracking is temporarily disabled due to Claude Code /usage format changes.
    The skip_limits and limits_from_db parameters are kept for API compatibility.

    Layout:
    ┌────────────────────────────────────────┐
    │           ◆ CLAUDE USAGE ◆            │
    │     1.2M tokens │ 847 prompts │ 23 sess│
    ├────────────────────────────────────────┤
    │          ◈ Activity Heatmap           │
    │  [heatmap grid + stats]                │
    ├───────────────────┬────────────────────┤
    │   ◈ Models        │   ◈ Branches       │
    ├───────────────────┴────────────────────┤
    │   ◈ Projects                           │
    └────────────────────────────────────────┘
    """
    if clear_screen:
        console.clear()

    # Header with key metrics
    header = _create_header(stats, records)
    console.print(header)

    # Activity heatmap (the hero component)
    heatmap = _create_heatmap(records)
    console.print(heatmap)
    console.print()

    # Model and branch breakdowns side by side
    model_panel = _create_model_breakdown(records)
    branch_panel = _create_branch_breakdown(records)

    # Use columns for side-by-side layout
    console.print(Columns([model_panel, branch_panel], equal=True, expand=True))
    console.print()

    # Project breakdown
    project_panel = _create_project_breakdown(records)
    console.print(project_panel)
    console.print()

    # Footer
    footer = _create_footer(date_range, fast_mode)
    console.print(footer)
#endregion
