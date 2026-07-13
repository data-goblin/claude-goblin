#region Imports
import platform
from pathlib import Path

from rich.console import Console

from src.utils._system import get_sound_command

#endregion


#region Functions


def setup(console: Console, settings: dict, settings_path: Path) -> None:
    """
    Set up the audio notification hook.

    Args:
        console: Rich console for output
        settings: Settings dictionary to modify
        settings_path: Path to settings.json file
    """
    # Offer sound choices
    console.print("[bold cyan]Choose notification sounds:[/bold cyan]\n")
    console.print("[dim]You'll pick three sounds: completion, permission requests, and conversation compaction[/dim]\n")

    # Check if audio-tts hook exists
    if "Notification" in settings.get("hooks", {}):
        from src.hooks import audio_tts
        existing_tts_hooks = [hook for hook in settings["hooks"]["Notification"] if audio_tts.is_hook(hook)]
        if existing_tts_hooks:
            console.print("[yellow]⚠ Warning: You already have an audio TTS hook configured.[/yellow]")
            console.print("[yellow]Setting up audio will replace it with simple sound notifications.[/yellow]\n")
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

    system = platform.system()
    if system == "Darwin":
        sounds = [
            ("Glass", "Clear glass sound (recommended for completion)"),
            ("Ping", "Short ping sound (recommended for permission)"),
            ("Purr", "Soft purr sound"),
            ("Tink", "Quick tink sound"),
            ("Pop", "Pop sound"),
            ("Basso", "Low bass sound"),
            ("Blow", "Blow sound"),
            ("Bottle", "Bottle sound"),
            ("Frog", "Frog sound"),
            ("Funk", "Funk sound"),
        ]
    elif system == "Windows":
        sounds = [
            ("Windows Notify", "Default notification"),
            ("Windows Ding", "Ding sound"),
            ("chimes", "Chimes sound"),
            ("chord", "Chord sound"),
            ("notify", "System notify"),
        ]
    else:  # Linux
        sounds = [
            ("complete", "Completion sound"),
            ("bell", "Bell sound"),
            ("message", "Message sound"),
            ("dialog-information", "Info dialog"),
            ("service-login", "Login sound"),
        ]

    # Choose completion sound
    console.print("[bold]Sound for when Claude finishes responding:[/bold]")
    for idx, (name, desc) in enumerate(sounds, 1):
        console.print(f"  {idx}. {name} - {desc}")

    console.print("\n[dim]Enter number (default: 1):[/dim] ", end="")

    try:
        user_input = input().strip()
        if user_input == "":
            completion_sound = sounds[0][0]
        elif user_input.isdigit() and 1 <= int(user_input) <= len(sounds):
            completion_sound = sounds[int(user_input) - 1][0]
        else:
            console.print("[yellow]Invalid selection, using default[/yellow]")
            completion_sound = sounds[0][0]
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    # Choose permission sound
    console.print("\n[bold]Sound for when Claude requests permission:[/bold]")
    for idx, (name, desc) in enumerate(sounds, 1):
        console.print(f"  {idx}. {name} - {desc}")

    console.print("\n[dim]Enter number (default: 2):[/dim] ", end="")

    try:
        user_input = input().strip()
        if user_input == "":
            # Default to second sound if available
            permission_sound = sounds[1][0] if len(sounds) > 1 else sounds[0][0]
        elif user_input.isdigit() and 1 <= int(user_input) <= len(sounds):
            permission_sound = sounds[int(user_input) - 1][0]
        else:
            console.print("[yellow]Invalid selection, using default[/yellow]")
            permission_sound = sounds[1][0] if len(sounds) > 1 else sounds[0][0]
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    # Choose compaction sound
    console.print("\n[bold]Sound for before conversation compaction:[/bold]")
    for idx, (name, desc) in enumerate(sounds, 1):
        console.print(f"  {idx}. {name} - {desc}")

    console.print("\n[dim]Enter number (default: 3):[/dim] ", end="")

    try:
        user_input = input().strip()
        if user_input == "":
            # Default to third sound if available
            compaction_sound = sounds[2][0] if len(sounds) > 2 else sounds[0][0]
        elif user_input.isdigit() and 1 <= int(user_input) <= len(sounds):
            compaction_sound = sounds[int(user_input) - 1][0]
        else:
            console.print("[yellow]Invalid selection, using default[/yellow]")
            compaction_sound = sounds[2][0] if len(sounds) > 2 else sounds[0][0]
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    completion_command = get_sound_command(completion_sound)
    permission_command = get_sound_command(permission_sound)
    compaction_command = get_sound_command(compaction_sound)

    if not completion_command or not permission_command or not compaction_command:
        console.print("[red]Audio hooks not supported on this platform[/red]")
        return

    # Initialize hook structures
    if "Stop" not in settings["hooks"]:
        settings["hooks"]["Stop"] = []
    if "Notification" not in settings["hooks"]:
        settings["hooks"]["Notification"] = []
    if "PreCompact" not in settings["hooks"]:
        settings["hooks"]["PreCompact"] = []

    # Remove existing audio hooks
    stop_removed = len(settings["hooks"]["Stop"])
    notification_removed = len(settings["hooks"]["Notification"])
    precompact_removed = len(settings["hooks"]["PreCompact"])

    settings["hooks"]["Stop"] = [
        hook for hook in settings["hooks"]["Stop"]
        if not is_hook(hook)
    ]
    # Remove both regular audio hooks and TTS hooks
    from src.hooks import audio_tts
    settings["hooks"]["Notification"] = [
        hook for hook in settings["hooks"]["Notification"]
        if not is_hook(hook) and not audio_tts.is_hook(hook)
    ]
    settings["hooks"]["PreCompact"] = [
        hook for hook in settings["hooks"]["PreCompact"]
        if not is_hook(hook) and not audio_tts.is_hook(hook)
    ]

    stop_removed = stop_removed > len(settings["hooks"]["Stop"])
    notification_removed = notification_removed > len(settings["hooks"]["Notification"])
    precompact_removed = precompact_removed > len(settings["hooks"]["PreCompact"])

    # Add new hooks
    settings["hooks"]["Stop"].append({
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": completion_command
        }]
    })

    settings["hooks"]["Notification"].append({
        "hooks": [{
            "type": "command",
            "command": permission_command
        }]
    })

    settings["hooks"]["PreCompact"].append({
        "hooks": [{
            "type": "command",
            "command": compaction_command
        }]
    })

    if stop_removed or notification_removed or precompact_removed:
        console.print("[cyan]Replaced existing audio notification hooks[/cyan]")

    console.print("[green]✓ Successfully configured audio notification hooks[/green]")
    console.print("\n[bold]What this does:[/bold]")
    console.print(f"  • Completion sound ({completion_sound}): Plays when Claude finishes responding")
    console.print(f"  • Permission sound ({permission_sound}): Plays when Claude requests permission")
    console.print(f"  • Compaction sound ({compaction_sound}): Plays before conversation compaction")
    console.print("  • All hooks run in the background")


def is_hook(hook) -> bool:
    """
    Check if a hook is an audio notification hook.

    Args:
        hook: Hook configuration dictionary

    Returns:
        True if this is an audio notification hook, False otherwise
    """
    if not isinstance(hook, dict) or "hooks" not in hook:
        return False
    for h in hook.get("hooks", []):
        cmd = h.get("command", "")
        if any(audio_cmd in cmd for audio_cmd in ["afplay", "powershell", "paplay", "aplay"]):
            return True
    return False


#endregion
