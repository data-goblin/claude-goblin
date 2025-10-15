"""
Setup module for awesome-hooks (https://github.com/boxabirds/awesome-hooks).

This module provides functionality to install PreToolUse hooks from the awesome-hooks
repository and custom hooks for Python/uv enforcement.
"""

#region Imports
import shutil
from pathlib import Path
from typing import Optional

from rich.console import Console
#endregion


#region Constants


# Hook types available
HOOK_TYPES = {
    "bundler-standard": {
        "name": "bundler-standard",
        "description": "Enforce Bun instead of npm/pnpm/yarn",
        "file": "bundler-standard.ts",
        "matcher": "Bash",
        "requires": "Bun runtime (https://bun.sh)",
        "command": "#!/usr/bin/env bun",
    },
    "file-name-consistency": {
        "name": "file-name-consistency",
        "description": "Ensure consistent file naming conventions",
        "file": "file-name-consistency.sh",
        "matcher": "Bash|Write|MultiEdit",
        "requires": "GEMINI_API_KEY environment variable",
        "command": "#!/bin/bash",
    },
    "uv-standard": {
        "name": "uv-standard",
        "description": "Enforce uv instead of pip/pip3",
        "file": "uv-standard.py",
        "matcher": "Bash",
        "requires": "uv package installer (https://github.com/astral-sh/uv)",
        "command": "#!/usr/bin/env python3",
    },
}


#endregion


#region Functions


def get_hook_install_path(user: bool = False) -> Path:
    """
    Get the installation path for awesome-hooks.

    Args:
        user: If True, install to user level (~/.claude/), otherwise project level (.claude/)

    Returns:
        Path to hook installation directory

    Purpose:
        Provides a centralized location for installed hook scripts.
    """
    if user:
        return Path.home() / ".claude" / "awesome-hooks"
    else:
        return Path.cwd() / ".claude" / "hooks"


def copy_hook_to_install_dir(hook_type: str, user: bool = False) -> Path:
    """
    Copy a hook script from the package to the install directory.

    Args:
        hook_type: Type of hook to copy (bundler-standard, file-name-consistency, uv-standard)
        user: If True, install to user level (~/.claude/), otherwise project level (.claude/)

    Returns:
        Path to the installed hook script

    Purpose:
        Copies hook scripts from the package hooks_data/ directory to the appropriate location.

    Raises:
        FileNotFoundError: If the source hook file doesn't exist
    """
    if hook_type not in HOOK_TYPES:
        raise ValueError(f"Unknown hook type: {hook_type}")

    hook_info = HOOK_TYPES[hook_type]
    install_dir = get_hook_install_path(user=user)
    install_dir.mkdir(parents=True, exist_ok=True)

    # Source is in the package's hooks_data/ directory
    package_root = Path(__file__).parent.parent
    source_path = package_root / "hooks_data" / hook_info["file"]

    if not source_path.exists():
        raise FileNotFoundError(f"Hook file not found: {source_path}")

    # Destination is in the appropriate hooks directory
    dest_path = install_dir / hook_info["file"]

    # Copy the file
    shutil.copy2(source_path, dest_path)

    # Make executable
    dest_path.chmod(0o755)

    return dest_path


def setup_bundler_standard(console: Console, settings: dict, settings_path: Path, user: bool = False) -> None:
    """
    Set up the bundler-standard hook (Bun enforcement).

    Args:
        console: Rich console for output
        settings: Settings dictionary to modify
        settings_path: Path to settings.json file
        user: If True, install at user level, otherwise project level

    Purpose:
        Installs and configures the bundler-standard hook to enforce Bun usage.
    """
    hook_path = copy_hook_to_install_dir("bundler-standard", user=user)

    # Initialize PreToolUse hooks structure
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    # Check if already exists
    hook_exists = any(is_bundler_standard_hook(hook) for hook in settings["hooks"]["PreToolUse"])

    if hook_exists:
        console.print("[yellow]bundler-standard hook already configured![/yellow]")
        return

    # Add hook
    settings["hooks"]["PreToolUse"].append({
        "matcher": "Bash",
        "hooks": [{
            "type": "command",
            "command": str(hook_path)
        }]
    })

    console.print("[green]✓ Successfully configured bundler-standard hook[/green]")
    console.print("\n[bold]What this does:[/bold]")
    console.print("  • Intercepts npm/pnpm/yarn commands in Bash")
    console.print("  • Blocks them and suggests Bun equivalents")
    console.print("  • Ensures you use Bun for package management\n")
    console.print("[bold cyan]Requirements:[/bold cyan]")
    console.print("  • Bun runtime installed (https://bun.sh)")


def setup_file_name_consistency(console: Console, settings: dict, settings_path: Path, user: bool = False) -> None:
    """
    Set up the file-name-consistency hook.

    Args:
        console: Rich console for output
        settings: Settings dictionary to modify
        settings_path: Path to settings.json file
        user: If True, install at user level, otherwise project level

    Purpose:
        Installs and configures the file-name-consistency hook for naming standards.
    """
    hook_path = copy_hook_to_install_dir("file-name-consistency", user=user)

    # Initialize PreToolUse hooks structure
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    # Check if already exists
    hook_exists = any(is_file_name_consistency_hook(hook) for hook in settings["hooks"]["PreToolUse"])

    if hook_exists:
        console.print("[yellow]file-name-consistency hook already configured![/yellow]")
        return

    # Add hook
    settings["hooks"]["PreToolUse"].append({
        "matcher": "Bash|Write|MultiEdit",
        "hooks": [{
            "type": "command",
            "command": str(hook_path)
        }]
    })

    console.print("[green]✓ Successfully configured file-name-consistency hook[/green]")
    console.print("\n[bold]What this does:[/bold]")
    console.print("  • Analyzes your project's file naming patterns")
    console.print("  • Blocks files with inconsistent naming")
    console.print("  • Suggests correctly formatted filenames\n")
    console.print("[bold cyan]Requirements:[/bold cyan]")
    console.print("  • GEMINI_API_KEY environment variable")
    console.print("  • Get your key at: https://aistudio.google.com/apikey\n")
    console.print("[bold yellow]Note:[/bold yellow]")
    console.print("  Set GEMINI_API_KEY in your shell profile:")
    console.print('  export GEMINI_API_KEY="your-api-key-here"')


def setup_uv_standard(console: Console, settings: dict, settings_path: Path, user: bool = False) -> None:
    """
    Set up the uv-standard hook (uv enforcement).

    Args:
        console: Rich console for output
        settings: Settings dictionary to modify
        settings_path: Path to settings.json file
        user: If True, install at user level, otherwise project level

    Purpose:
        Installs and configures the uv-standard hook to enforce uv usage.
    """
    hook_path = copy_hook_to_install_dir("uv-standard", user=user)

    # Initialize PreToolUse hooks structure
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    # Check if already exists
    hook_exists = any(is_uv_standard_hook(hook) for hook in settings["hooks"]["PreToolUse"])

    if hook_exists:
        console.print("[yellow]uv-standard hook already configured![/yellow]")
        return

    # Add hook
    settings["hooks"]["PreToolUse"].append({
        "matcher": "Bash",
        "hooks": [{
            "type": "command",
            "command": str(hook_path)
        }]
    })

    console.print("[green]✓ Successfully configured uv-standard hook[/green]")
    console.print("\n[bold]What this does:[/bold]")
    console.print("  • Intercepts pip/pip3 commands in Bash")
    console.print("  • Blocks them and suggests uv equivalents")
    console.print("  • Ensures you use uv for Python package management\n")
    console.print("[bold cyan]Requirements:[/bold cyan]")
    console.print("  • uv package installer (https://github.com/astral-sh/uv)")
    console.print("  • Install with: curl -LsSf https://astral.sh/uv/install.sh | sh")


def is_bundler_standard_hook(hook: dict) -> bool:
    """
    Check if a hook is the bundler-standard hook.

    Args:
        hook: Hook configuration dictionary

    Returns:
        True if this is the bundler-standard hook, False otherwise
    """
    if not isinstance(hook, dict) or "hooks" not in hook:
        return False
    for h in hook.get("hooks", []):
        command = h.get("command", "")
        if "bundler-standard" in command:
            return True
    return False


def is_file_name_consistency_hook(hook: dict) -> bool:
    """
    Check if a hook is the file-name-consistency hook.

    Args:
        hook: Hook configuration dictionary

    Returns:
        True if this is the file-name-consistency hook, False otherwise
    """
    if not isinstance(hook, dict) or "hooks" not in hook:
        return False
    for h in hook.get("hooks", []):
        command = h.get("command", "")
        if "file-name-consistency" in command:
            return True
    return False


def is_uv_standard_hook(hook: dict) -> bool:
    """
    Check if a hook is the uv-standard hook.

    Args:
        hook: Hook configuration dictionary

    Returns:
        True if this is the uv-standard hook, False otherwise
    """
    if not isinstance(hook, dict) or "hooks" not in hook:
        return False
    for h in hook.get("hooks", []):
        command = h.get("command", "")
        if "uv-standard" in command:
            return True
    return False


def setup(console: Console, settings: dict, settings_path: Path, hook_type: Optional[str] = None, user: bool = False) -> None:
    """
    Set up awesome-hooks.

    Args:
        console: Rich console for output
        settings: Settings dictionary to modify
        settings_path: Path to settings.json file
        hook_type: Specific hook type to set up, or None to show menu
        user: If True, install at user level, otherwise project level

    Purpose:
        Main entry point for setting up awesome-hooks. Delegates to specific setup functions.
    """
    if hook_type is None:
        # Show menu
        console.print("[bold cyan]Available awesome-hooks:[/bold cyan]\n")
        for key, info in HOOK_TYPES.items():
            console.print(f"  [bold]{key}[/bold]")
            console.print(f"    {info['description']}")
            console.print(f"    [dim]Requires: {info['requires']}[/dim]\n")
        console.print("Usage: ccg setup-hooks <hook-name> [--user]")
        console.print("Example: ccg setup-hooks uv-standard       (project-level)")
        console.print("Example: ccg setup-hooks uv-standard --user (user-level)")
        return

    # Delegate to specific setup function
    if hook_type == "bundler-standard":
        setup_bundler_standard(console, settings, settings_path, user=user)
    elif hook_type == "file-name-consistency":
        setup_file_name_consistency(console, settings, settings_path, user=user)
    elif hook_type == "uv-standard":
        setup_uv_standard(console, settings, settings_path, user=user)
    else:
        console.print(f"[red]Unknown hook type: {hook_type}[/red]")
        console.print("Valid types: bundler-standard, file-name-consistency, uv-standard")


def remove(console: Console, settings: dict, hook_type: Optional[str] = None) -> bool:
    """
    Remove awesome-hooks from settings.

    Args:
        console: Rich console for output
        settings: Settings dictionary to modify
        hook_type: Specific hook type to remove, or None for all

    Returns:
        True if any hooks were removed, False otherwise

    Purpose:
        Removes awesome-hooks from the Claude Code settings.
    """
    if "PreToolUse" not in settings.get("hooks", {}):
        return False

    original_count = len(settings["hooks"]["PreToolUse"])

    if hook_type == "bundler-standard":
        settings["hooks"]["PreToolUse"] = [
            hook for hook in settings["hooks"]["PreToolUse"]
            if not is_bundler_standard_hook(hook)
        ]
    elif hook_type == "file-name-consistency":
        settings["hooks"]["PreToolUse"] = [
            hook for hook in settings["hooks"]["PreToolUse"]
            if not is_file_name_consistency_hook(hook)
        ]
    elif hook_type == "uv-standard":
        settings["hooks"]["PreToolUse"] = [
            hook for hook in settings["hooks"]["PreToolUse"]
            if not is_uv_standard_hook(hook)
        ]
    else:
        # Remove all awesome-hooks
        settings["hooks"]["PreToolUse"] = [
            hook for hook in settings["hooks"]["PreToolUse"]
            if not (is_bundler_standard_hook(hook) or
                   is_file_name_consistency_hook(hook) or
                   is_uv_standard_hook(hook))
        ]

    removed_count = original_count - len(settings["hooks"]["PreToolUse"])
    return removed_count > 0


#endregion
