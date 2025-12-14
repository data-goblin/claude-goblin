#region Imports
import shutil
from pathlib import Path

from rich.console import Console

from src.config.user_config import get_storage_mode, set_storage_mode
from src.storage.snapshot_db import DEFAULT_DB_PATH
#endregion


#region Functions


def setup(console: Console, settings: dict, settings_path: Path) -> None:
    """
    Set up the usage tracking hook.

    Args:
        console: Rich console for output
        settings: Settings dictionary to modify
        settings_path: Path to settings.json file
    """
    # Check current storage mode
    current_mode = get_storage_mode()

    # Ask user to choose storage mode
    console.print("[bold cyan]Choose storage mode:[/bold cyan]\n")
    console.print("  [bold]1. Aggregate (default)[/bold] - Daily totals only (smaller, faster)")
    console.print("     • Stores: date, prompts count, tokens totals")
    console.print("     • ~10-50 KB for a year of data")
    console.print("     • Good for: Activity tracking, usage trends\n")
    console.print("  [bold]2. Full Analytics[/bold] - Every individual message (larger, detailed)")
    console.print("     • Stores: every prompt with model, folder, timestamps")
    console.print("     • ~5-10 MB for a year of heavy usage")
    console.print("     • Good for: Detailed analysis, per-project breakdowns\n")

    if current_mode == "full":
        console.print(f"[dim]Current mode: Full Analytics[/dim]")
    else:
        console.print(f"[dim]Current mode: Aggregate[/dim]")

    console.print("[dim]Enter 1 or 2 (or press Enter for default):[/dim] ", end="")

    try:
        user_input = input().strip()
        if user_input == "2":
            storage_mode = "full"
        else:
            storage_mode = "aggregate"
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    hook_command = "ccg update usage > /dev/null 2>&1 &"

    # Check if already exists
    hook_exists = any(is_hook(hook) for hook in settings["hooks"]["Stop"])

    # Warn if changing storage modes
    if current_mode != storage_mode and hook_exists:
        console.print("\n[bold yellow]⚠️  WARNING: Changing storage mode[/bold yellow]")
        console.print(f"[yellow]Current mode: {current_mode.title()}[/yellow]")
        console.print(f"[yellow]New mode: {storage_mode.title()}[/yellow]")
        console.print("")

        if current_mode == "full" and storage_mode == "aggregate":
            console.print("[yellow]• New data will only save daily totals (no individual messages)[/yellow]")
            console.print("[yellow]• Existing detailed records will remain but won't be updated[/yellow]")
        else:
            console.print("[yellow]• New data will save full details for each message[/yellow]")
            console.print("[yellow]• Historical aggregates will still be available[/yellow]")

        console.print("")
        console.print("[bold cyan]Would you like to create a backup of your database?[/bold cyan]")
        console.print(f"[dim]Database: {DEFAULT_DB_PATH}[/dim]")
        console.print("[dim]Backup will be saved as: usage_history.db.bak[/dim]")
        console.print("")
        console.print("[cyan]Create backup? (yes/no) [recommended: yes]:[/cyan] ", end="")

        try:
            backup_choice = input().strip().lower()
            if backup_choice in ["yes", "y"]:
                # Create backup
                backup_path = DEFAULT_DB_PATH.parent / "usage_history.db.bak"

                if DEFAULT_DB_PATH.exists():
                    shutil.copy2(DEFAULT_DB_PATH, backup_path)
                    console.print(f"[green]✓ Backup created: {backup_path}[/green]")
                    console.print(f"[dim]To restore: ccg restore usage[/dim]")
                else:
                    console.print("[yellow]No database file found to backup[/yellow]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Cancelled[/yellow]")
            return

        console.print("")
        console.print("[cyan]Continue with mode change? (yes/no):[/cyan] ", end="")

        try:
            confirm = input().strip().lower()
            if confirm not in ["yes", "y"]:
                console.print(f"[yellow]Cancelled - keeping current mode ({current_mode})[/yellow]")
                return
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Cancelled[/yellow]")
            return

    # Save storage mode preference
    set_storage_mode(storage_mode)

    if hook_exists:
        console.print(f"\n[yellow]Usage tracking hook already configured![/yellow]")
        console.print(f"[cyan]Storage mode updated to: {storage_mode}[/cyan]")
        return

    # Add hook
    settings["hooks"]["Stop"].append({
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": hook_command
        }]
    })

    console.print(f"[green]✓ Successfully configured usage tracking hook ({storage_mode} mode)[/green]")
    console.print("\n[bold]What this does:[/bold]")
    console.print("  • Runs after each Claude response completes")
    if storage_mode == "aggregate":
        console.print("  • Saves daily usage totals (lightweight)")
    else:
        console.print("  • Saves every individual message (detailed analytics)")
    console.print("  • Fills in gaps with empty records")
    console.print("  • Runs silently in the background")


def is_hook(hook) -> bool:
    """
    Check if a hook is a usage tracking hook.

    Recognizes both old-style (--update-usage) and new-style (update-usage) commands.

    Args:
        hook: Hook configuration dictionary

    Returns:
        True if this is a usage tracking hook, False otherwise
    """
    if not isinstance(hook, dict) or "hooks" not in hook:
        return False
    for h in hook.get("hooks", []):
        command = h.get("command", "")
        # Support old-style (--update-usage, update-usage) and new-style (update usage)
        # Also support both claude-goblin and ccg aliases
        if ("claude-goblin --update-usage" in command or "claude-goblin update-usage" in command or
            "claude-goblin update usage" in command or
            "ccg --update-usage" in command or "ccg update-usage" in command or
            "ccg update usage" in command):
            return True
    return False


#endregion
