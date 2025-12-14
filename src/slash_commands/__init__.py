"""
Bundled slash commands for Claude Code.

Slash commands are prompt templates that get installed to ~/.claude/commands/
and provide quick access to common workflows.
"""

from pathlib import Path

COMMANDS_DIR = Path(__file__).parent

# Available bundled commands
AVAILABLE_COMMANDS = {
    "review": {
        "file": "review.md",
        "description": "Review current changes for issues and improvements",
    },
    "commit": {
        "file": "commit.md",
        "description": "Generate a conventional commit message",
    },
    "test": {
        "file": "test.md",
        "description": "Run tests and analyze results",
    },
}


def get_command_path(command_name: str) -> Path | None:
    """Get the path to a bundled command file."""
    if command_name not in AVAILABLE_COMMANDS:
        return None
    return COMMANDS_DIR / AVAILABLE_COMMANDS[command_name]["file"]


def list_commands() -> dict:
    """List all available bundled commands."""
    return AVAILABLE_COMMANDS
