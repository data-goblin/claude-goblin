"""
Setup commands command for Claude Goblin.

Installs bundled slash commands to ~/.claude/commands/ for quick workflow access.
"""
from pathlib import Path
from typing import Optional
import shutil

import typer
from rich.console import Console
from rich.table import Table

from src.slash_commands import AVAILABLE_COMMANDS, get_command_path


console = Console()

# Default commands installation directory
CLAUDE_COMMANDS_DIR = Path.home() / ".claude" / "commands"


def setup_commands_command(
    command_name: Optional[str] = typer.Argument(
        None,
        help="Name of command to install (or 'all' for all commands)",
    ),
    list_commands: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List available bundled commands",
    ),
    user: bool = typer.Option(
        True,
        "--user/--project",
        help="Install to user directory (~/.claude/commands) or project (.claude/commands)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing command files",
    ),
):
    """
    Install bundled slash commands for Claude Code.

    Slash commands are prompt templates that provide quick access to
    common workflows like reviewing code, generating commits, and running tests.

    Examples:
        ccg setup commands --list              List available commands
        ccg setup commands review              Install review command
        ccg setup commands all                 Install all bundled commands
        ccg setup commands test --project      Install to project directory
    """
    if list_commands or command_name is None:
        _list_available_commands()
        return

    # Determine installation directory
    if user:
        commands_dir = CLAUDE_COMMANDS_DIR
    else:
        commands_dir = Path.cwd() / ".claude" / "commands"

    # Install all commands or specific command
    if command_name == "all":
        _install_all_commands(commands_dir, force)
    else:
        _install_command(command_name, commands_dir, force)


def _list_available_commands():
    """Display table of available bundled commands."""
    table = Table(title="Available Bundled Commands")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Usage", style="dim")

    for name, info in AVAILABLE_COMMANDS.items():
        table.add_row(name, info["description"], f"/{name}")

    console.print(table)
    console.print()
    console.print("Install with: [cyan]ccg setup commands <name>[/cyan]")
    console.print("Install all:  [cyan]ccg setup commands all[/cyan]")
    console.print()
    console.print("[dim]After installation, use commands in Claude Code with /name[/dim]")


def _install_command(command_name: str, commands_dir: Path, force: bool):
    """Install a single command."""
    if command_name not in AVAILABLE_COMMANDS:
        console.print(f"[red]Error:[/red] Unknown command '{command_name}'")
        console.print("Use [cyan]ccg setup commands --list[/cyan] to see available commands")
        raise typer.Exit(1)

    source_path = get_command_path(command_name)
    if source_path is None or not source_path.exists():
        console.print(f"[red]Error:[/red] Command file not found for '{command_name}'")
        raise typer.Exit(1)

    # Create target directory
    commands_dir.mkdir(parents=True, exist_ok=True)

    # Copy command file
    target_path = commands_dir / AVAILABLE_COMMANDS[command_name]["file"]

    if target_path.exists() and not force:
        console.print(f"[yellow]Warning:[/yellow] {target_path} already exists")
        console.print("Use [cyan]--force[/cyan] to overwrite")
        return

    shutil.copy2(source_path, target_path)
    console.print(f"[green]Installed:[/green] /{command_name} -> {target_path}")
    console.print(f"[dim]Use in Claude Code: /{command_name}[/dim]")


def _install_all_commands(commands_dir: Path, force: bool):
    """Install all bundled commands."""
    console.print(f"Installing all commands to {commands_dir}...")

    commands_dir.mkdir(parents=True, exist_ok=True)

    installed = 0
    skipped = 0

    for command_name in AVAILABLE_COMMANDS:
        source_path = get_command_path(command_name)
        if source_path is None or not source_path.exists():
            console.print(f"[yellow]Warning:[/yellow] Command file not found: {command_name}")
            continue

        target_path = commands_dir / AVAILABLE_COMMANDS[command_name]["file"]

        if target_path.exists() and not force:
            console.print(f"[dim]Skipped:[/dim] /{command_name} (already exists)")
            skipped += 1
            continue

        shutil.copy2(source_path, target_path)
        console.print(f"[green]Installed:[/green] /{command_name}")
        installed += 1

    console.print()
    console.print(f"Installed {installed} commands, skipped {skipped}")
    if skipped > 0:
        console.print("Use [cyan]--force[/cyan] to overwrite existing files")
    console.print()
    console.print("[dim]Use commands in Claude Code with /<name>[/dim]")
