"""
Claude Goblin CLI - Command-line interface using typer.

Main entry point for all claude-goblin commands.
"""
from typing import Optional
import typer
from rich.console import Console

from src.commands import (
    usage,
    stats,
    export,
    help as help_cmd,
    limits,
    status_bar,
)
from src.commands.setup import app as setup_app
from src.commands.remove import app as remove_app
from src.commands.update import app as update_app
from src.commands.restore import app as restore_app


# Version
__version__ = "0.1.10"


# Create typer app
app = typer.Typer(
    name="claude-goblin",
    help="Python CLI for Claude Code utilities and usage tracking/analytics",
    add_completion=False,
    no_args_is_help=True,
)


# Add sub-apps for nested commands
app.add_typer(setup_app, name="setup")
app.add_typer(remove_app, name="remove")
app.add_typer(update_app, name="update")
app.add_typer(restore_app, name="restore")


def version_callback(value: bool):
    """Callback for --version flag."""
    if value:
        console = Console()
        console.print(f"claude-goblin version {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    )
):
    """Claude Goblin CLI callback for global options."""
    pass

# Create console for commands
console = Console()


@app.command(name="usage")
def usage_command(
    live: bool = typer.Option(False, "--live", help="Auto-refresh dashboard every 5 seconds"),
    fast: bool = typer.Option(False, "--fast", help="Skip updates, read from database only (faster)"),
    anon: bool = typer.Option(False, "--anon", help="Anonymize project names to project-001, project-002, etc"),
):
    """
    Show usage dashboard with KPI cards and breakdowns.

    Displays comprehensive usage statistics including:
    - Total tokens, prompts, and sessions
    - Current usage limits (session, weekly, Opus)
    - Token breakdown by model
    - Token breakdown by project

    Use --live for auto-refreshing dashboard.
    Use --fast to skip all updates and read from database only (requires existing database).
    Use --anon to anonymize project names (ranked by usage, project-001 is highest).
    """
    usage.run(console, live=live, fast=fast, anon=anon)


@app.command(name="stats")
def stats_command(
    fast: bool = typer.Option(False, "--fast", help="Skip updates, read from database only (faster)"),
):
    """
    Show detailed statistics and cost analysis.

    Displays comprehensive statistics including:
    - Summary: total tokens, prompts, responses, sessions, days tracked
    - Cost analysis: estimated API costs vs Max Plan costs
    - Averages: tokens per session/response, cost per session/response
    - Text analysis: prompt length, politeness markers, phrase counts
    - Usage by model: token distribution across different models

    Use --fast to skip all updates and read from database only (requires existing database).
    """
    stats.run(console, fast=fast)


@app.command(name="limits")
def limits_command():
    """
    Show current usage limits (session, week, Opus).

    Displays current usage percentages and reset times for:
    - Session limit (resets after inactivity)
    - Weekly limit for all models (resets weekly)
    - Weekly Opus limit (resets weekly)

    Note: Must be run from a trusted folder where Claude Code has been used.
    """
    limits.run(console)


@app.command(name="export")
def export_command(
    svg: bool = typer.Option(False, "--svg", help="Export as SVG instead of PNG"),
    open_file: bool = typer.Option(False, "--open", help="Open file after export"),
    fast: bool = typer.Option(False, "--fast", help="Skip updates, read from database only (faster)"),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Filter by year (default: current year)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    show: Optional[str] = typer.Option("tokens", "--show", "-s", help="What to show: tokens, limits, or both (default: tokens)"),
):
    """
    Export yearly heatmap as PNG or SVG.

    Generates a GitHub-style activity heatmap showing your Claude Code usage
    throughout the year. By default exports as PNG showing token usage only.

    Use --fast to skip all updates and read from database only (requires existing database).
    Use --show to control what's displayed (tokens, limits, or both).

    Examples:
        ccg export --open                  Export current year as PNG and open it
        ccg export --svg                   Export as SVG instead
        ccg export --fast                  Export from database without updating
        ccg export -y 2024                 Export specific year
        ccg export -o ~/usage.png          Specify output path
        ccg export --show both             Show tokens + limits
        ccg export --show limits           Show only limits (week % and opus %)
    """
    # Validate show parameter
    if show not in ["tokens", "limits", "both"]:
        console.print(f"[red]Error: Invalid --show value '{show}'[/red]")
        console.print("[yellow]Valid values: tokens, limits, both[/yellow]")
        raise typer.Exit(1)

    # Pass parameters via sys.argv for backward compatibility with export command
    import sys
    if svg and "svg" not in sys.argv:
        sys.argv.append("svg")
    if open_file and "--open" not in sys.argv:
        sys.argv.append("--open")
    if fast and "--fast" not in sys.argv:
        sys.argv.append("--fast")
    if year is not None:
        if "--year" not in sys.argv and "-y" not in sys.argv:
            sys.argv.extend(["--year", str(year)])
    if output is not None:
        if "--output" not in sys.argv and "-o" not in sys.argv:
            sys.argv.extend(["--output", output])
    if show is not None:
        if "--show" not in sys.argv and "-s" not in sys.argv:
            sys.argv.extend(["--show", show])

    export.run(console)


@app.command(name="status-bar")
def status_bar_command(
    limit_type: str = typer.Argument("weekly", help="Type of limit to display: session, weekly, or opus"),
):
    """
    Launch macOS menu bar app (macOS only).

    Displays "CC: XX%" in your menu bar, showing current usage percentage.
    Updates automatically every 5 minutes.

    Arguments:
        limit_type: Which limit to display (session, weekly, or opus). Defaults to weekly.

    Examples:
        ccg status-bar weekly    Show weekly usage (default)
        ccg status-bar session   Show session usage
        ccg status-bar opus      Show Opus weekly usage

    Running in background:
        nohup ccg status-bar weekly > /dev/null 2>&1 &
    """
    if limit_type not in ["session", "weekly", "opus"]:
        console.print(f"[red]Error: Invalid limit type '{limit_type}'[/red]")
        console.print("[yellow]Valid types: session, weekly, opus[/yellow]")
        raise typer.Exit(1)

    status_bar.run(console, limit_type)


@app.command(name="help", hidden=True)
def help_command():
    """
    Show detailed help message.

    Displays comprehensive usage information including:
    - Available commands and their flags
    - Key features of the tool
    - Data sources and storage locations
    - Recommended setup workflow
    """
    help_cmd.run(console)


def main() -> None:
    """
    Main CLI entry point for Claude Goblin Usage tracker.

    Loads Claude Code usage data and provides commands for viewing,
    analyzing, and exporting usage statistics.

    Usage:
        ccg --help              Show available commands
        ccg usage               Show usage dashboard
        ccg usage --live        Show dashboard with auto-refresh
        ccg stats               Show detailed statistics
        ccg export              Export yearly heatmap

    Exit:
        Press Ctrl+C to exit
    """
    app()


if __name__ == "__main__":
    main()
