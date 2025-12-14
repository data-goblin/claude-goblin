"""
Remove hooks command.

Removes Claude Code hooks configured by this tool.
"""
from typing import Optional
import typer
from rich.console import Console

from src.hooks.manager import remove_hooks as _remove_hooks


def remove_hooks_command(
    hook_type: Optional[str] = typer.Argument(
        None,
        help="Hook type to remove: usage, audio, audio-tts, png, bundler-standard, file-name-consistency, uv-standard, or leave empty for all"
    ),
    user: bool = typer.Option(
        False,
        "--user",
        help="Remove hooks from user level (~/.claude/) instead of project level (.claude/)"
    ),
) -> None:
    """
    Remove Claude Code hooks configured by this tool.

    By default, removes hooks from project level (.claude/settings.json in current directory).
    Use --user to remove from user level (~/.claude/settings.json).

    Examples:
        ccg remove hooks                    Remove all hooks (project-level)
        ccg remove hooks --user             Remove all hooks (user-level)
        ccg remove hooks usage              Remove only usage tracking hook
        ccg remove hooks audio              Remove only audio notification hook
        ccg remove hooks audio-tts          Remove only audio TTS hook
        ccg remove hooks png                Remove only PNG export hook
        ccg remove hooks uv-standard        Remove only uv-standard hook
        ccg remove hooks bundler-standard   Remove only bundler-standard hook
    """
    console = Console()
    _remove_hooks(console, hook_type, user=user)
