# 007: Interactive TUI for Claude Management

## Summary
Create an interactive TUI for setup and headless Claude Code management, allowing users to review and update memory, skills, commands, and other primitives.

## Features

### Main Menu
```
+------------------------------------------+
|        Claude Goblin Setup TUI           |
+------------------------------------------+
| [1] Manage Memory                        |
| [2] Manage Skills                        |
| [3] Manage Commands                      |
| [4] Configure Hooks                      |
| [5] View/Edit Settings                   |
| [6] Usage Dashboard                      |
| [q] Quit                                 |
+------------------------------------------+
```

### Memory Management
- View current CLAUDE.md content
- Edit sections interactively
- Add/remove memory entries
- Call Claude headlessly to suggest improvements

### Skills Management
- List available skills
- Enable/disable skills
- View skill documentation
- Install new skills from registry

### Commands Management
- List custom slash commands
- Create new commands
- Edit existing commands
- Test commands

### Headless Claude Integration
```python
def ask_claude_to_review(content: str, aspect: str) -> str:
    """Call Claude Code headlessly to review content."""
    # Use subprocess to call claude with piped input
    # Parse and return suggestions
```

## Implementation

### TUI Framework
- Use `textual` for rich TUI
- Or `prompt_toolkit` for simpler interface
- Keyboard navigation
- Mouse support optional

### File Locations
- Memory: `~/.claude/CLAUDE.md`, `.claude/CLAUDE.md`
- Skills: `~/.claude/skills/`
- Commands: `~/.claude/commands/`
- Settings: `~/.claude/settings.json`

## Tasks
- [ ] Design TUI layout and navigation
- [ ] Implement main menu
- [ ] Implement memory viewer/editor
- [ ] Implement skills manager
- [ ] Implement commands manager
- [ ] Add headless Claude integration
- [ ] Add settings editor
- [ ] Create `ccg tui` command entry point
