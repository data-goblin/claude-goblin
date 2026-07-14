#region Imports
import platform
from pathlib import Path

from rich.console import Console

#endregion


#region Functions


def setup(console: Console, settings: dict, settings_path: Path) -> None:
    """
    Set up the audio TTS notification hook.

    Speaks messages using the system's text-to-speech engine (macOS 'say' command).

    Args:
        console: Rich console for output
        settings: Settings dictionary to modify
        settings_path: Path to settings.json file
    """
    # Check if macOS (currently only supports macOS 'say' command)
    system = platform.system()
    if system != "Darwin":
        console.print("[red]Error: Audio TTS hook is currently only supported on macOS[/red]")
        console.print("[yellow]Requires the 'say' command which is macOS-specific[/yellow]")
        return

    console.print("[bold cyan]Setting up Audio TTS Hook[/bold cyan]\n")
    console.print("[dim]This hook speaks messages aloud using macOS text-to-speech.[/dim]\n")

    # Check if regular audio notification hook exists
    if "Notification" in settings.get("hooks", {}) or "Stop" in settings.get("hooks", {}) or "PreCompact" in settings.get("hooks", {}):
        from src.hooks import audio
        existing_audio_hooks = []
        for hook_type in ["Notification", "Stop", "PreCompact"]:
            if hook_type in settings.get("hooks", {}):
                existing_audio_hooks.extend([hook for hook in settings["hooks"][hook_type] if audio.is_hook(hook)])

        if existing_audio_hooks:
            console.print("[yellow]⚠ Warning: You already have audio notification hooks configured.[/yellow]")
            console.print("[yellow]Setting up audio-tts will replace them with TTS notifications.[/yellow]\n")
            console.print("[dim]Continue? (y/n):[/dim] ", end="")
            try:
                user_input = input().strip().lower()
                if user_input != "y":
                    console.print("[yellow]Cancelled[/yellow]")
                    return
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]Cancelled[/yellow]")
                return
            console.print()

    # Hook type selection
    console.print("[bold]Which hooks do you want to enable TTS for?[/bold]")
    console.print("  1. Notification only (permission requests) [recommended]")
    console.print("  2. Stop only (when Claude finishes responding)")
    console.print("  3. PreCompact only (before conversation compaction)")
    console.print("  4. Notification + Stop")
    console.print("  5. Notification + PreCompact")
    console.print("  6. Stop + PreCompact")
    console.print("  7. All three (Notification + Stop + PreCompact)")

    console.print("\n[dim]Enter number (default: 1 - Notification only):[/dim] ", end="")

    try:
        user_input = input().strip()
        if user_input == "" or user_input == "1":
            hook_types = ["Notification"]
        elif user_input == "2":
            hook_types = ["Stop"]
        elif user_input == "3":
            hook_types = ["PreCompact"]
        elif user_input == "4":
            hook_types = ["Notification", "Stop"]
        elif user_input == "5":
            hook_types = ["Notification", "PreCompact"]
        elif user_input == "6":
            hook_types = ["Stop", "PreCompact"]
        elif user_input == "7":
            hook_types = ["Notification", "Stop", "PreCompact"]
        else:
            console.print("[yellow]Invalid selection, using default (Notification only)[/yellow]")
            hook_types = ["Notification"]
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    console.print()

    # Voice selection
    console.print("[bold]Choose a voice for TTS:[/bold]")
    voices = [
        ("Samantha", "Clear, natural female voice (recommended)"),
        ("Alex", "Clear, natural male voice"),
        ("Daniel", "British English male voice"),
        ("Karen", "Australian English female voice"),
        ("Moira", "Irish English female voice"),
        ("Fred", "Classic robotic voice"),
        ("Zarvox", "Sci-fi robotic voice"),
    ]

    for idx, (name, desc) in enumerate(voices, 1):
        console.print(f"  {idx}. {name} - {desc}")

    console.print("\n[dim]Enter number (default: 1 - Samantha):[/dim] ", end="")

    try:
        user_input = input().strip()
        if user_input == "":
            voice = voices[0][0]
        elif user_input.isdigit() and 1 <= int(user_input) <= len(voices):
            voice = voices[int(user_input) - 1][0]
        else:
            console.print("[yellow]Invalid selection, using default (Samantha)[/yellow]")
            voice = voices[0][0]
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    # Get path to the TTS hook script
    hook_script = Path(__file__).parent / "scripts" / "audio_tts_hook.sh"

    # Create the hook script if it doesn't exist
    hook_script.parent.mkdir(parents=True, exist_ok=True)

    # Write the hook script with selected voice
    hook_script_content = f"""#!/bin/bash
# Audio TTS Hook for Claude Code
# Reads hook JSON from stdin and speaks it using macOS 'say'

# Read JSON from stdin
json_input=$(cat)

# Extract the message content from the JSON
# Try different fields depending on hook type
message=$(echo "$json_input" | python3 -c "
import sys
import json
try:
    data = json.load(sys.stdin)
    hook_type = data.get('hook_event_name', '')

    # Get appropriate message based on hook type
    if hook_type == 'Notification':
        msg = data.get('message', 'Claude requesting permission')
    elif hook_type == 'Stop':
        msg = 'Claude finished responding'
    elif hook_type == 'PreCompact':
        trigger = data.get('trigger', 'unknown')
        if trigger == 'auto':
            msg = 'Auto compacting conversation'
        else:
            msg = 'Manually compacting conversation'
    else:
        msg = data.get('message', 'Claude event')

    print(msg)
except:
    print('Claude event')
")

# Speak the message using macOS 'say' with selected voice (run in background to avoid blocking)
echo "$message" | say -v {voice} &

# Optional: Log for debugging
# echo "$(date): TTS spoke: $message" >> ~/.claude/tts_hook.log
"""

    hook_script.write_text(hook_script_content, encoding="utf-8")
    hook_script.chmod(0o755)  # Make executable

    # Initialize hook structures
    for hook_type in ["Notification", "Stop", "PreCompact"]:
        if hook_type not in settings["hooks"]:
            settings["hooks"][hook_type] = []

    # Remove existing TTS hooks and regular audio hooks from selected hook types
    removed_count = 0
    for hook_type in hook_types:
        original_count = len(settings["hooks"][hook_type])
        settings["hooks"][hook_type] = [
            hook for hook in settings["hooks"][hook_type]
            if not is_hook(hook) and not _is_audio_hook(hook)
        ]
        removed_count += original_count - len(settings["hooks"][hook_type])

    # Add new TTS hook to selected hook types
    for hook_type in hook_types:
        hook_config = {
            "hooks": [{
                "type": "command",
                "command": str(hook_script.absolute())
            }]
        }

        # Add matcher for Stop hook
        if hook_type == "Stop":
            hook_config["matcher"] = "*"

        settings["hooks"][hook_type].append(hook_config)

    if removed_count > 0:
        console.print(f"[cyan]Replaced {removed_count} existing audio notification hook(s)[/cyan]")

    console.print("[green]✓ Successfully configured audio TTS hooks[/green]")
    console.print("\n[bold]What this does:[/bold]")
    for hook_type in hook_types:
        if hook_type == "Notification":
            console.print("  • Notification: Speaks permission request messages aloud")
        elif hook_type == "Stop":
            console.print("  • Stop: Announces when Claude finishes responding")
        elif hook_type == "PreCompact":
            console.print("  • PreCompact: Announces before conversation compaction")
    console.print(f"  • Uses the '{voice}' voice")
    console.print("  • Runs in background to avoid blocking Claude Code")
    console.print(f"\n[dim]Hook script: {hook_script}[/dim]")


def _is_audio_hook(hook) -> bool:
    """
    Check if a hook is a regular audio notification hook (not TTS).

    Args:
        hook: Hook configuration dictionary

    Returns:
        True if this is a regular audio notification hook, False otherwise
    """
    if not isinstance(hook, dict) or "hooks" not in hook:
        return False
    for h in hook.get("hooks", []):
        cmd = h.get("command", "")
        if any(audio_cmd in cmd for audio_cmd in ["afplay", "powershell", "paplay", "aplay"]) and "audio_tts_hook.sh" not in cmd:
            return True
    return False


def is_hook(hook) -> bool:
    """
    Check if a hook is an audio TTS notification hook.

    Args:
        hook: Hook configuration dictionary

    Returns:
        True if this is an audio TTS notification hook, False otherwise
    """
    if not isinstance(hook, dict) or "hooks" not in hook:
        return False
    for h in hook.get("hooks", []):
        cmd = h.get("command", "")
        if "audio_tts_hook.sh" in cmd:
            return True
    return False


#endregion
