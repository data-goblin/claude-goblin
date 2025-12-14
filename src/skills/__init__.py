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
    """Parse YAML frontmatter from SKILL.md file (simple parser, no yaml dep)."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return {}

    content = skill_md.read_text()

    # Extract YAML frontmatter between --- markers
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    # Simple YAML parsing for name/description (avoids pyyaml dependency)
    frontmatter = {}
    for line in match.group(1).split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key in ('name', 'description', 'version'):
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

    # Remove existing skill if present
    if target_skill_dir.exists():
        shutil.rmtree(target_skill_dir)

    # Copy skill directory
    shutil.copytree(skill_path, target_skill_dir)

    return True


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
