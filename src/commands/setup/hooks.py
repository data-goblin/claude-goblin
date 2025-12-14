"""
Setup hooks command.

Sets up Claude Code hooks for automation.
"""
from typing import Optional
import typer
from rich.console import Console

from src.hooks.manager import setup_hooks as _setup_hooks


def setup_hooks_command(
    hook_type: Optional[str] = typer.Argument(
        None,
        help="Hook type: usage, audio, audio-tts, png, bundler-standard, file-name-consistency, or uv-standard"
    ),
    user: bool = typer.Option(
        False,
        "--user",
        help="Install hooks at user level (~/.claude/) instead of project level (.claude/)"
    ),
) -> None:
    """
    Setup Claude Code hooks for automation.

    By default, hooks are installed at the project level (.claude/settings.json in current directory).
    Use --user to install at user level (~/.claude/settings.json for all projects).

    Available Claude Goblin hooks:
    - usage: Auto-track usage after each Claude response
    - audio: Play sounds for completion, permission, and compaction (3 sounds)
    - audio-tts: Speak messages using TTS with hook selection (macOS only)
    - png: Auto-update usage PNG after each Claude response

    Available awesome-hooks (PreToolUse):
    - bundler-standard: Enforce Bun instead of npm/pnpm/yarn
    - file-name-consistency: Ensure consistent file naming conventions
    - uv-standard: Enforce uv instead of pip/pip3

    Examples:
        ccg setup hooks usage              Enable usage tracking (project-level)
        ccg setup hooks usage --user       Enable usage tracking (user-level)
        ccg setup hooks audio              Enable audio notifications
        ccg setup hooks audio-tts          Enable TTS (choose which hooks)
        ccg setup hooks png                Enable automatic PNG exports
        ccg setup hooks uv-standard        Enforce uv for Python packages
        ccg setup hooks bundler-standard   Enforce Bun for JS packages
    """
    console = Console()
    _setup_hooks(console, hook_type, user=user)
