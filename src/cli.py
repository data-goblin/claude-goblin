"""
Claude Goblin CLI - Command-line interface using typer.

Main entry point for all claude-goblin commands.
"""

import sys

# Consoles that aren't UTF-8 -- Windows cp1252, or a POSIX box pinned to a
# non-UTF-8 locale -- make rich raise UnicodeEncodeError the moment output
# contains a non-ASCII glyph (e.g. the warning triangle used by `update usage`),
# aborting commands mid-run. Force UTF-8 on the std streams before any rich
# Console is constructed. UTF-8 encodes every code point, so this can never
# itself raise; the guard only covers streams that aren't reconfigurable
# (e.g. replaced with StringIO under test capture).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

import typer
from rich.console import Console

from src.commands import (
    export,
    stats,
    usage,
)
from src.commands import (
    help as help_cmd,
)
from src.commands.container import app as container_app
from src.commands.remove import app as remove_app
from src.commands.restore import app as restore_app
from src.commands.setup import app as setup_app
from src.commands.sync import app as sync_app
from src.commands.update import app as update_app

# Version
__version__ = "1.2.0"


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
app.add_typer(sync_app, name="sync")
app.add_typer(container_app, name="container")


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
    force: bool = typer.Option(False, "--force", help="Force re-parse all JSONL files (may take 4-5s for large histories)"),
    remote: bool = typer.Option(False, "--remote", "-r", help="Query the remote DuckDB server instead of local"),
):
    """
    Show usage dashboard with KPI cards and breakdowns.

    Displays comprehensive usage statistics including:
    - Total tokens, prompts, and sessions
    - Token breakdown by model
    - Token breakdown by project

    Use --live for auto-refreshing dashboard.
    Use --fast to skip all updates and read from database only (requires existing database).
    Use --anon to anonymize project names (ranked by usage, project-001 is highest).
    Use --force to bypass incremental parsing cache and re-parse all JSONL files.
        Note: May take 4-5 seconds for large histories. Use when data seems stale.
        In --live mode, --force only applies to the first refresh.
    Use --remote to query the remote server (shows cross-device aggregate data).
    """
    if remote:
        usage.run_remote(console, anon=anon)
    else:
        usage.run(console, live=live, fast=fast, anon=anon, force=force)


@app.command(name="stats")
def stats_command(
    fast: bool = typer.Option(False, "--fast", help="Skip updates, read from database only (faster)"),
    force: bool = typer.Option(False, "--force", help="Force re-parse all JSONL files (may take 4-5s for large histories)"),
    remote: bool = typer.Option(False, "--remote", "-r", help="Query the remote DuckDB server instead of local"),
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
    Use --force to bypass incremental parsing cache and re-parse all JSONL files.
        Note: May take 4-5 seconds for large histories. Use when data seems stale.
    Use --remote to query the remote server (shows cross-device aggregate data).
    """
    if remote:
        stats.run_remote(console)
    else:
        stats.run(console, fast=fast, force=force)


@app.command(name="export")
def export_command(
    svg: bool = typer.Option(False, "--svg", help="Export as SVG instead of PNG"),
    open_file: bool = typer.Option(False, "--open", help="Open file after export"),
    fast: bool = typer.Option(False, "--fast", help="Skip updates, read from database only (faster)"),
    year: int | None = typer.Option(None, "--year", "-y", help="Filter by year (default: current year)"),
    output: str | None = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """
    Export yearly heatmap as PNG or SVG.

    Generates a GitHub-style activity heatmap showing your Claude Code usage
    throughout the year. By default exports as PNG.

    Use --fast to skip all updates and read from database only (requires existing database).

    Examples:
        ccg export --open                  Export current year as PNG and open it
        ccg export --svg                   Export as SVG instead
        ccg export --fast                  Export from database without updating
        ccg export -y 2024                 Export specific year
        ccg export -o ~/usage.png          Specify output path
    """
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
    export.run(console)


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


@app.command(name="tui")
def tui_command():
    """
    Launch interactive TUI dashboard.

    Opens a rich terminal user interface for viewing and managing
    Claude Code usage statistics. Requires textual to be installed.

    Install with: pip install claude-goblin[tui]

    Features:
    - Real-time usage statistics
    - Activity heatmap
    - Model breakdown table
    - Interactive navigation

    Keys:
        r - Refresh data
        d - Dashboard view
        q - Quit
        ? - Help
    """
    try:
        from src.tui import run_tui
        run_tui()
    except ImportError:
        console.print("[red]Error:[/red] Textual is not installed.")
        console.print("Install with: [cyan]pip install claude-goblin[tui][/cyan]")
        raise typer.Exit(1)


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
