"""
Bundled skills for Claude Code.

Skills are self-contained directories that get installed to ~/.claude/skills/
and help Claude Code perform specific tasks more effectively.

Each skill directory contains:
- SKILL.md (required): Main skill definition with YAML frontmatter
- references/ (optional): Documentation and reference material
- scripts/ (optional): Executable utilities
- assets/ (optional): Templates and resources
"""

from pathlib import Path
import shutil
import re

SKILLS_DIR = Path(__file__).parent


def _parse_skill_frontmatter(skill_path: Path) -> dict:
    """
    Parse YAML frontmatter from SKILL.md file.

    Uses a simple parser that handles common cases without pyyaml dependency.
    Supports:
    - Simple key: value pairs
    - Quoted values (single or double quotes)
    - Colons within quoted values
    - Multi-line values are NOT supported (first line only)

    Args:
        skill_path: Path to skill directory containing SKILL.md

    Returns:
        Dictionary with parsed frontmatter fields (name, description, version)
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return {}

    content = skill_md.read_text()

    # Extract YAML frontmatter between --- markers
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    frontmatter = {}
    for line in match.group(1).split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Match key: value pattern, handling quoted values with colons
        # Pattern: key: "value with: colons" or key: 'value with: colons' or key: simple value
        key_match = re.match(r'^(\w+):\s*(.*)$', line)
        if not key_match:
            continue

        key = key_match.group(1).strip()
        value = key_match.group(2).strip()

        # Only parse fields we care about
        if key not in ('name', 'description', 'version'):
            continue

        # Handle quoted strings (preserves colons inside quotes)
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]

        frontmatter[key] = value

    return frontmatter


def discover_skills() -> dict:
    """
    Discover all bundled skills in the skills directory.

    Returns:
        Dictionary of skill_name -> skill_info
    """
    skills = {}

    for item in SKILLS_DIR.iterdir():
        if item.is_dir() and (item / "SKILL.md").exists():
            frontmatter = _parse_skill_frontmatter(item)
            skills[item.name] = {
                "path": item,
                "name": frontmatter.get("name", item.name),
                "description": frontmatter.get("description", ""),
                "has_scripts": (item / "scripts").exists(),
                "has_references": (item / "references").exists(),
                "has_assets": (item / "assets").exists(),
            }

    return skills


# Available bundled skills (discovered at import time)
AVAILABLE_SKILLS = discover_skills()


def get_skill_path(skill_name: str) -> Path | None:
    """Get the path to a bundled skill directory."""
    if skill_name not in AVAILABLE_SKILLS:
        return None
    return AVAILABLE_SKILLS[skill_name]["path"]


def list_skills() -> dict:
    """List all available bundled skills."""
    return AVAILABLE_SKILLS


def install_skill(skill_name: str, target_dir: Path | None = None) -> bool:
    """
    Install a bundled skill to the user's Claude skills directory.

    Uses atomic operations to ensure the skill directory is never left in
    an inconsistent state. If installation fails, any existing skill is preserved.

    Args:
        skill_name: Name of the skill to install
        target_dir: Target directory (defaults to ~/.claude/skills/)

    Returns:
        True if installation succeeded, False otherwise
    """
    if skill_name not in AVAILABLE_SKILLS:
        return False

    skill_path = AVAILABLE_SKILLS[skill_name]["path"]
    if target_dir is None:
        target_dir = Path.home() / ".claude" / "skills"

    target_dir.mkdir(parents=True, exist_ok=True)
    target_skill_dir = target_dir / skill_name

    # Use temporary directory for atomic installation
    temp_dir = target_dir / f".{skill_name}.installing"
    backup_dir = target_dir / f".{skill_name}.backup"

    try:
        # Clean up any leftover temp/backup dirs from failed installs
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

        # Copy to temp location first
        shutil.copytree(skill_path, temp_dir)

        # Backup existing skill if present (atomic rename)
        if target_skill_dir.exists():
            target_skill_dir.rename(backup_dir)

        # Move temp to final location (atomic on same filesystem)
        temp_dir.rename(target_skill_dir)

        # Remove backup on success
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

        return True

    except (OSError, shutil.Error):
        # Restore backup if it exists
        if backup_dir.exists():
            if target_skill_dir.exists():
                shutil.rmtree(target_skill_dir)
            backup_dir.rename(target_skill_dir)

        # Clean up temp dir
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        return False


def install_all_skills(target_dir: Path | None = None) -> list[str]:
    """
    Install all bundled skills.

    Args:
        target_dir: Target directory (defaults to ~/.claude/skills/)

    Returns:
        List of successfully installed skill names
    """
    installed = []
    for skill_name in AVAILABLE_SKILLS:
        if install_skill(skill_name, target_dir):
            installed.append(skill_name)
    return installed
