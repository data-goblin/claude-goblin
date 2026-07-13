"""
Update usage command.

Updates historical database with latest data.
"""
import typer
from rich.console import Console

from src.commands import update_usage as _update_usage_module


def update_usage_command(
    push: bool = typer.Option(False, "--push", help="Push new records to the configured remote after updating"),
    rebuild: bool = typer.Option(
        False, "--rebuild",
        help="Repair: re-ingest every session still on disk under the corrected "
             "billed-response identity (backs up the DB first; blocks quack pushes "
             "until the remote is purged)",
    ),
) -> None:
    """
    Update historical database with latest data.

    This command:
    1. Saves current usage data from JSONL files
    2. Fills in missing days with zero-usage records
    3. Ensures complete date coverage from earliest record to today

    Useful for ensuring continuous heatmap data without gaps.

    Examples:
        ccg update usage             Update the usage database
        ccg update usage --push      Update, then push to the remote in one process
        ccg update usage --rebuild   Repair inflated history from surviving transcripts
    """
    console = Console()
    if rebuild:
        _update_usage_module.rebuild_token_usage(console)
        return
    _update_usage_module.run(console)
    if push:
        from src.commands.sync.push import run_push
        run_push(console, strict=False)
