"""
Bundled skills for Claude Code.

Skills are instruction files that get installed to ~/.claude/skills/
and help Claude Code perform specific tasks more effectively.
"""

from pathlib import Path

SKILLS_DIR = Path(__file__).parent

# Available bundled skills
AVAILABLE_SKILLS = {
    "test-generator": {
        "file": "test_generator.md",
        "description": "Generate comprehensive unit tests for Python code",
    },
    "commit-writer": {
        "file": "commit_writer.md",
        "description": "Write conventional commit messages",
    },
    "changelog-updater": {
        "file": "changelog_updater.md",
        "description": "Update CHANGELOG.md following Keep a Changelog format",
    },
}


def get_skill_path(skill_name: str) -> Path | None:
    """Get the path to a bundled skill file."""
    if skill_name not in AVAILABLE_SKILLS:
        return None
    return SKILLS_DIR / AVAILABLE_SKILLS[skill_name]["file"]


def list_skills() -> dict:
    """List all available bundled skills."""
    return AVAILABLE_SKILLS
