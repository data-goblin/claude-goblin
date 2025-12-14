"""
Interactive TUI module for Claude Goblin.

Provides a rich terminal user interface for managing Claude Code
utilities and viewing usage statistics.

Requires: pip install claude-goblin[tui]
"""

from src.tui.app import run_tui

__all__ = ["run_tui"]
