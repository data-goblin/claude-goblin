#region Imports
import json
from pathlib import Path
from typing import Optional

from rich.console import Console

from src.hooks import usage, audio, png, audio_tts, awesome_hooks
#endregion


#region Functions


def setup_hooks(console: Console, hook_type: Optional[str] = None, user: bool = False) -> None:
    """
    Set up Claude Code hooks for automation.

    Args:
        console: Rich console for output
        hook_type: Type of hook to set up ('usage', 'audio', 'png', or None for menu)
        user: If True, install at user level (~/.claude/), otherwise project level (.claude/)
    """
    if user:
        settings_path = Path.home() / ".claude" / "settings.json"
        scope = "user"
    else:
        settings_path = Path.cwd() / ".claude" / "settings.json"
        scope = "project"

    if hook_type is None:
        # Show menu
        console.print("[bold cyan]Available hooks to set up:[/bold cyan]\n")
        console.print("[bold]Claude Goblin hooks:[/bold]")
        console.print("  [bold]usage[/bold]                - Auto-track usage after each response")
        console.print("  [bold]audio[/bold]                - Play sounds for completion & permission requests")
        console.print("  [bold]audio-tts[/bold]            - Speak permission requests using TTS (macOS only)")
        console.print("  [bold]png[/bold]                  - Auto-update usage PNG after each response\n")
        console.print("[bold]Awesome-hooks (PreToolUse):[/bold]")
        console.print("  [bold]bundler-standard[/bold]     - Enforce Bun instead of npm/pnpm/yarn")
        console.print("  [bold]file-name-consistency[/bold] - Ensure consistent file naming")
        console.print("  [bold]uv-standard[/bold]          - Enforce uv instead of pip/pip3\n")
        console.print("Usage: ccg setup-hooks <type> [--user]")
        console.print("Example: ccg setup-hooks usage              (project-level)")
        console.print("Example: ccg setup-hooks usage --user       (user-level)")
        console.print("Example: ccg setup-hooks uv-standard        (project-level)")
        return

    console.print(f"[bold cyan]Setting up {hook_type} hook ({scope}-level)[/bold cyan]\n")

    try:
        # Ensure .claude directory exists
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing settings
        if settings_path.exists():
            with open(settings_path, "r") as f:
                settings = json.load(f)
        else:
            settings = {}

        # Initialize hooks structure
        if "hooks" not in settings:
            settings["hooks"] = {}

        if "Stop" not in settings["hooks"]:
            settings["hooks"]["Stop"] = []

        if "Notification" not in settings["hooks"]:
            settings["hooks"]["Notification"] = []

        # Delegate to specific hook module
        if hook_type == "usage":
            usage.setup(console, settings, settings_path)
        elif hook_type == "audio":
            audio.setup(console, settings, settings_path)
        elif hook_type == "audio-tts":
            audio_tts.setup(console, settings, settings_path)
        elif hook_type == "png":
            png.setup(console, settings, settings_path)
        elif hook_type in ["bundler-standard", "file-name-consistency", "uv-standard"]:
            awesome_hooks.setup(console, settings, settings_path, hook_type, user=user)
        else:
            console.print(f"[red]Unknown hook type: {hook_type}[/red]")
            console.print("Valid types: usage, audio, audio-tts, png, bundler-standard, file-name-consistency, uv-standard")
            return

        # Write settings back
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

        console.print(f"\n[dim]Hook location: {settings_path}[/dim]")
        console.print(f"[dim]To remove: ccg remove-hooks {hook_type}{' --user' if user else ''}[/dim]")

    except Exception as e:
        console.print(f"[red]Error setting up hooks: {e}[/red]")
        import traceback
        traceback.print_exc()


def remove_hooks(console: Console, hook_type: Optional[str] = None, user: bool = False) -> None:
    """
    Remove Claude Code hooks configured by this tool.

    Args:
        console: Rich console for output
        hook_type: Type of hook to remove ('usage', 'audio', 'png', or None for all)
        user: If True, remove from user level (~/.claude/), otherwise project level (.claude/)
    """
    if user:
        settings_path = Path.home() / ".claude" / "settings.json"
        scope = "user"
    else:
        settings_path = Path.cwd() / ".claude" / "settings.json"
        scope = "project"

    if not settings_path.exists():
        console.print(f"[yellow]No Claude Code settings file found at {scope} level.[/yellow]")
        return

    console.print(f"[bold cyan]Removing hooks ({scope}-level)[/bold cyan]\n")

    try:
        # Read existing settings
        with open(settings_path, "r") as f:
            settings = json.load(f)

        if "hooks" not in settings:
            console.print("[yellow]No hooks configured.[/yellow]")
            return

        # Initialize hook lists if they don't exist
        if "Stop" not in settings["hooks"]:
            settings["hooks"]["Stop"] = []
        if "Notification" not in settings["hooks"]:
            settings["hooks"]["Notification"] = []
        if "PreCompact" not in settings["hooks"]:
            settings["hooks"]["PreCompact"] = []
        if "PreToolUse" not in settings["hooks"]:
            settings["hooks"]["PreToolUse"] = []

        original_stop_count = len(settings["hooks"]["Stop"])
        original_notification_count = len(settings["hooks"]["Notification"])
        original_precompact_count = len(settings["hooks"]["PreCompact"])
        original_pretooluse_count = len(settings["hooks"]["PreToolUse"])

        # Remove hooks based on type
        if hook_type == "usage":
            settings["hooks"]["Stop"] = [
                hook for hook in settings["hooks"]["Stop"]
                if not usage.is_hook(hook)
            ]
            removed_type = "usage tracking"
        elif hook_type == "audio":
            settings["hooks"]["Stop"] = [
                hook for hook in settings["hooks"]["Stop"]
                if not audio.is_hook(hook)
            ]
            settings["hooks"]["Notification"] = [
                hook for hook in settings["hooks"]["Notification"]
                if not audio.is_hook(hook)
            ]
            settings["hooks"]["PreCompact"] = [
                hook for hook in settings["hooks"]["PreCompact"]
                if not audio.is_hook(hook)
            ]
            removed_type = "audio notification"
        elif hook_type == "audio-tts":
            settings["hooks"]["Notification"] = [
                hook for hook in settings["hooks"]["Notification"]
                if not audio_tts.is_hook(hook)
            ]
            settings["hooks"]["Stop"] = [
                hook for hook in settings["hooks"]["Stop"]
                if not audio_tts.is_hook(hook)
            ]
            settings["hooks"]["PreCompact"] = [
                hook for hook in settings["hooks"]["PreCompact"]
                if not audio_tts.is_hook(hook)
            ]
            removed_type = "audio TTS"
        elif hook_type == "png":
            settings["hooks"]["Stop"] = [
                hook for hook in settings["hooks"]["Stop"]
                if not png.is_hook(hook)
            ]
            removed_type = "PNG auto-update"
        elif hook_type in ["bundler-standard", "file-name-consistency", "uv-standard"]:
            awesome_hooks.remove(console, settings, hook_type)
            removed_type = hook_type
        else:
            # Remove all our hooks
            settings["hooks"]["Stop"] = [
                hook for hook in settings["hooks"]["Stop"]
                if not (usage.is_hook(hook) or audio.is_hook(hook) or png.is_hook(hook))
            ]
            settings["hooks"]["Notification"] = [
                hook for hook in settings["hooks"]["Notification"]
                if not (usage.is_hook(hook) or audio.is_hook(hook) or png.is_hook(hook) or audio_tts.is_hook(hook))
            ]
            settings["hooks"]["PreCompact"] = [
                hook for hook in settings["hooks"]["PreCompact"]
                if not (audio.is_hook(hook) or audio_tts.is_hook(hook))
            ]
            # Also remove awesome-hooks
            awesome_hooks.remove(console, settings, None)
            removed_type = "all claude-goblin"

        removed_count = (original_stop_count - len(settings["hooks"]["Stop"])) + \
                       (original_notification_count - len(settings["hooks"]["Notification"])) + \
                       (original_precompact_count - len(settings["hooks"]["PreCompact"])) + \
                       (original_pretooluse_count - len(settings["hooks"].get("PreToolUse", [])))

        if removed_count == 0:
            console.print(f"[yellow]No {removed_type} hooks found to remove.[/yellow]")
            return

        # Write settings back
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

        console.print(f"[green]✓ Removed {removed_count} {removed_type} hook(s)[/green]")
        console.print(f"[dim]Settings file: {settings_path}[/dim]")

    except Exception as e:
        console.print(f"[red]Error removing hooks: {e}[/red]")
        import traceback
        traceback.print_exc()


#endregion
