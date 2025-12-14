"""
Setup skills command for Claude Goblin.

Installs bundled skills to ~/.claude/skills/ for enhanced Claude Code capabilities.
"""
from pathlib import Path
from typing import Optional
import shutil

import typer
from rich.console import Console
from rich.table import Table

from src.skills import AVAILABLE_SKILLS, get_skill_path


console = Console()

# Default skills installation directory
CLAUDE_SKILLS_DIR = Path.home() / ".claude" / "skills"


def setup_skills_command(
    skill_name: Optional[str] = typer.Argument(
        None,
        help="Name of skill to install (or 'all' for all skills)",
    ),
    list_skills: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List available bundled skills",
    ),
    user: bool = typer.Option(
        True,
        "--user/--project",
        help="Install to user directory (~/.claude/skills) or project (.claude/skills)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing skill files",
    ),
):
    """
    Install bundled skills to enhance Claude Code capabilities.

    Skills are instruction files that help Claude Code perform specific
    tasks more effectively, like generating tests or writing commits.

    Examples:
        ccg setup skills --list              List available skills
        ccg setup skills test-generator      Install test generator skill
        ccg setup skills all                 Install all bundled skills
        ccg setup skills commit-writer --project  Install to project directory
    """
    if list_skills or skill_name is None:
        _list_available_skills()
        return

    # Determine installation directory
    if user:
        skills_dir = CLAUDE_SKILLS_DIR
    else:
        skills_dir = Path.cwd() / ".claude" / "skills"

    # Install all skills or specific skill
    if skill_name == "all":
        _install_all_skills(skills_dir, force)
    else:
        _install_skill(skill_name, skills_dir, force)


def _list_available_skills():
    """Display table of available bundled skills."""
    table = Table(title="Available Bundled Skills")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("File", style="dim")

    for name, info in AVAILABLE_SKILLS.items():
        table.add_row(name, info["description"], info["file"])

    console.print(table)
    console.print()
    console.print("Install with: [cyan]ccg setup skills <name>[/cyan]")
    console.print("Install all:  [cyan]ccg setup skills all[/cyan]")


def _install_skill(skill_name: str, skills_dir: Path, force: bool):
    """Install a single skill."""
    if skill_name not in AVAILABLE_SKILLS:
        console.print(f"[red]Error:[/red] Unknown skill '{skill_name}'")
        console.print("Use [cyan]ccg setup skills --list[/cyan] to see available skills")
        raise typer.Exit(1)

    source_path = get_skill_path(skill_name)
    if source_path is None or not source_path.exists():
        console.print(f"[red]Error:[/red] Skill file not found for '{skill_name}'")
        raise typer.Exit(1)

    # Create target directory
    try:
        skills_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        console.print(f"[red]Error:[/red] Cannot create directory {skills_dir}: {e}")
        raise typer.Exit(1)

    # Copy skill file
    target_path = skills_dir / AVAILABLE_SKILLS[skill_name]["file"]

    if target_path.exists() and not force:
        console.print(f"[yellow]Warning:[/yellow] {target_path} already exists")
        console.print("Use [cyan]--force[/cyan] to overwrite")
        return

    try:
        shutil.copy2(source_path, target_path)
        console.print(f"[green]Installed:[/green] {skill_name} -> {target_path}")
    except (OSError, PermissionError) as e:
        console.print(f"[red]Error:[/red] Cannot install {skill_name}: {e}")
        raise typer.Exit(1)


def _install_all_skills(skills_dir: Path, force: bool):
    """Install all bundled skills."""
    console.print(f"Installing all skills to {skills_dir}...")

    try:
        skills_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        console.print(f"[red]Error:[/red] Cannot create directory {skills_dir}: {e}")
        raise typer.Exit(1)

    installed = 0
    skipped = 0
    errors = 0

    for skill_name in AVAILABLE_SKILLS:
        source_path = get_skill_path(skill_name)
        if source_path is None or not source_path.exists():
            console.print(f"[yellow]Warning:[/yellow] Skill file not found: {skill_name}")
            continue

        target_path = skills_dir / AVAILABLE_SKILLS[skill_name]["file"]

        if target_path.exists() and not force:
            console.print(f"[dim]Skipped:[/dim] {skill_name} (already exists)")
            skipped += 1
            continue

        try:
            shutil.copy2(source_path, target_path)
            console.print(f"[green]Installed:[/green] {skill_name}")
            installed += 1
        except (OSError, PermissionError) as e:
            console.print(f"[red]Error:[/red] Cannot install {skill_name}: {e}")
            errors += 1

    console.print()
    console.print(f"Installed {installed} skills, skipped {skipped}")
    if errors > 0:
        console.print(f"[red]Failed to install {errors} skills[/red]")
    if skipped > 0:
        console.print("Use [cyan]--force[/cyan] to overwrite existing files")
