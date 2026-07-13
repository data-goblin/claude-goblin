#region Imports
from pathlib import Path
from typing import Final

#endregion


#region Constants
# Claude data directory
CLAUDE_DATA_DIR: Final[Path] = Path.home() / ".claude" / "projects"

# Default refresh interval for dashboard (seconds)
DEFAULT_REFRESH_INTERVAL: Final[int] = 5

# Number of days to show in activity graph
ACTIVITY_GRAPH_DAYS: Final[int] = 365

# Graph dimensions
GRAPH_WEEKS: Final[int] = 52  # 52 weeks = 364 days (close to 365)
GRAPH_DAYS_PER_WEEK: Final[int] = 7
#endregion


#region Functions


def get_claude_jsonl_files() -> list[Path]:
    """
    Get all JSONL files from Claude's project data directory.

    Returns:
        List of Path objects pointing to JSONL files

    Raises:
        FileNotFoundError: If Claude data directory doesn't exist
    """
    if not CLAUDE_DATA_DIR.exists():
        raise FileNotFoundError(
            f"Claude data directory not found at {CLAUDE_DATA_DIR}. "
            "Make sure Claude Code has been run at least once."
        )

    return list(CLAUDE_DATA_DIR.rglob("*.jsonl"))
#endregion
