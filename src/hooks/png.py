#region Imports
from pathlib import Path

from rich.console import Console

#endregion


#region Functions


def setup(console: Console, settings: dict, settings_path: Path) -> None:
    """
    Set up the PNG auto-update hook.

    Args:
        console: Rich console for output
        settings: Settings dictionary to modify
        settings_path: Path to settings.json file
    """
    # Ask for output path
    default_output = str(Path.home() / ".claude" / "usage" / "claude-usage.png")
    console.print("[bold cyan]Configure PNG auto-update:[/bold cyan]\n")
    console.print(f"[dim]Default output: {default_output}[/dim]")
    console.print("[dim]Enter custom path (or press Enter for default):[/dim] ", end="")

    try:
        user_input = input().strip()
        output_path = user_input if user_input else default_output
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    # Create directory if it doesn't exist
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    hook_command = f"ccg export -o {output_path} > /dev/null 2>&1 &"

    # Remove existing PNG hooks
    original_count = len(settings["hooks"]["Stop"])
    settings["hooks"]["Stop"] = [
        hook for hook in settings["hooks"]["Stop"]
        if not is_hook(hook)
    ]
    png_hook_removed = len(settings["hooks"]["Stop"]) < original_count

    # Add new hook
    settings["hooks"]["Stop"].append({
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": hook_command
        }]
    })

    if png_hook_removed:
        console.print("[cyan]Replaced existing PNG auto-update hook[/cyan]")

    console.print("[green]✓ Successfully configured PNG auto-update hook[/green]")
    console.print("\n[bold]What this does:[/bold]")
    console.print("  • Exports PNG after each Claude response completes")
    console.print(f"  • Overwrites: {output_path}")
    console.print("  • Runs silently in the background")


def is_hook(hook) -> bool:
    """
    Check if a hook is a PNG export hook.

    Recognizes both old-style (--export) and new-style (export) commands.

    Args:
        hook: Hook configuration dictionary

    Returns:
        True if this is a PNG export hook, False otherwise
    """
    if not isinstance(hook, dict) or "hooks" not in hook:
        return False
    for h in hook.get("hooks", []):
        cmd = h.get("command", "")
        # Support both old-style (--export) and new-style (export)
        # Also support both claude-goblin and ccg aliases
        if (("claude-goblin --export" in cmd or "claude-goblin export" in cmd or
             "ccg --export" in cmd or "ccg export" in cmd) and "-o" in cmd):
            return True
    return False


#endregion
