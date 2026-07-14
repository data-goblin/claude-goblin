#region Imports
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console

from src.aggregation.daily_stats import aggregate_all
from src.config.settings import get_claude_jsonl_files
from src.config.user_config import get_storage_mode
from src.data.jsonl_parser import parse_all_jsonl_files
from src.storage import api
from src.storage.api import (
    get_database_stats,
    load_historical_records,
    save_snapshot,
)
from src.utils._system import open_file

#endregion


#region Functions


def run(console: Console) -> None:
    """
    Export the heatmap to PNG or SVG.

    Exports a GitHub-style activity heatmap as an image file.
    Supports PNG (default) and SVG formats, with optional file opening.

    Args:
        console: Rich console for output

    Flags:
        svg: Export as SVG instead of PNG
        --open: Open file after export
        --fast: Skip updates, read directly from database (faster)
        --year YYYY or -y YYYY: Filter by year (default: current year)
        -o FILE or --output FILE: Specify output file path
    """
    from src.visualization.export import export_heatmap_png, export_heatmap_svg

    # Check for --fast flag
    fast_mode = "--fast" in sys.argv

    # Determine format from arguments (PNG is default)
    format_type = "png"
    if "svg" in sys.argv:
        format_type = "svg"

    # Check for --open flag
    should_open = "--open" in sys.argv

    # Parse year filter (--year YYYY)
    year_filter = None
    for i, arg in enumerate(sys.argv):
        if arg in ["--year", "-y"] and i + 1 < len(sys.argv):
            try:
                year_filter = int(sys.argv[i + 1])
            except ValueError:
                console.print(f"[red]Invalid year: {sys.argv[i + 1]}[/red]")
                return
            break

    # Default to current year if not specified
    if year_filter is None:
        year_filter = datetime.now().year

    # Determine output path
    output_file = None
    custom_output = False
    for i, arg in enumerate(sys.argv):
        if arg in ["-o", "--output"] and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            custom_output = True
            break

    if not output_file:
        output_file = f"claude-usage.{format_type}"

    # Use absolute path, or resolve based on whether -o flag was used
    output_path = Path(output_file)
    if not output_path.is_absolute():
        if custom_output:
            # If -o flag was used, resolve relative to current working directory
            output_path = Path.cwd() / output_path
        else:
            # Default location: ~/.claude/usage/
            default_dir = Path.home() / ".claude" / "usage"
            default_dir.mkdir(parents=True, exist_ok=True)
            output_path = default_dir / output_file

    try:
        # Check if database exists when using --fast
        if fast_mode and not api.current_db_path().exists():
            console.print("[red]Error: Cannot use --fast flag without existing database.[/red]")
            console.print("[yellow]Run 'ccg usage' or 'ccg update usage' first to create the database.[/yellow]")
            return

        # If fast mode, show warning with last update timestamp
        if fast_mode:
            db_stats = get_database_stats()
            if db_stats.get("newest_timestamp"):
                # Format ISO timestamp to be more readable
                timestamp_str = db_stats["newest_timestamp"]
                try:
                    dt = datetime.fromisoformat(timestamp_str)
                    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    console.print(f"[bold red]⚠ Fast mode: Reading from last update ({formatted_time})[/bold red]")
                except (ValueError, AttributeError):
                    console.print(f"[bold red]⚠ Fast mode: Reading from last update ({timestamp_str})[/bold red]")
            else:
                console.print("[bold red]⚠ Fast mode: Reading from database (no timestamp available)[/bold red]")

        # Update data unless in fast mode
        if not fast_mode:
            # Update usage data
            with console.status("[bold #ff8800]Updating usage data...", spinner="dots", spinner_style="#ff8800"):
                jsonl_files = get_claude_jsonl_files()
                if jsonl_files:
                    current_records = parse_all_jsonl_files(jsonl_files)
                    if current_records:
                        save_snapshot(current_records, storage_mode=get_storage_mode())

        # Load data from database
        with console.status(f"[bold #ff8800]Loading data for {year_filter}...", spinner="dots", spinner_style="#ff8800"):
            all_records = load_historical_records()

            if not all_records:
                console.print("[yellow]No usage data found in database. Run 'ccg usage' to ingest data first.[/yellow]")
                return

            stats = aggregate_all(all_records)

        console.print(f"[cyan]Exporting to {format_type.upper()}...[/cyan]")

        if format_type == "png":
            export_heatmap_png(stats, output_path, year=year_filter)
        else:
            export_heatmap_svg(stats, output_path, year=year_filter)

        console.print(f"[green]✓ Exported to: {output_path.absolute()}[/green]")

        # Open the file if --open flag is present
        if should_open:
            console.print(f"[cyan]Opening {format_type.upper()}...[/cyan]")
            open_file(output_path)

    except ImportError as e:
        console.print(f"[red]{e}[/red]")
    except Exception as e:
        console.print(f"[red]Error exporting: {e}[/red]")
        import traceback
        traceback.print_exc()


#endregion
