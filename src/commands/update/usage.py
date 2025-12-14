"""
Update usage command.

Updates historical database with latest data.
"""
import typer
from rich.console import Console

from src.commands import update_usage as _update_usage_module


def update_usage_command() -> None:
    """
    Update historical database with latest data.

    This command:
    1. Saves current usage data from JSONL files
    2. Fills in missing days with zero-usage records
    3. Ensures complete date coverage from earliest record to today

    Useful for ensuring continuous heatmap data without gaps.

    Examples:
        ccg update usage    Update the usage database
    """
    console = Console()
    _update_usage_module.run(console)
