# 009: Bundled Slash Commands for Claude Code

## Summary
Include useful custom slash commands that enhance Claude Code workflows, installable via `ccg setup commands`.

## Candidate Commands

### Development Commands
- **/review**: Review current changes for issues
- **/test**: Run tests and analyze failures
- **/lint**: Run linting and fix issues
- **/format**: Format code in current file/directory

### Git Commands
- **/commit**: Generate commit message and commit
- **/pr**: Create PR with generated description
- **/branch**: Create branch with conventional naming
- **/sync**: Fetch, rebase, and push

### Documentation Commands
- **/doc**: Generate documentation for selection
- **/explain**: Explain code in detail
- **/diagram**: Generate mermaid diagram

### Project Commands
- **/init**: Initialize project structure
- **/deps**: Analyze and update dependencies
- **/todo**: List and manage TODOs

## Implementation

### Command Format
```
~/.claude/commands/
  review.md
  commit.md
  pr.md
  ...
```

### Command Definition
```markdown
---
description: Review current changes for issues
arguments:
  - name: scope
    description: What to review (file, staged, all)
    default: staged
---

Review the following changes for:
- Bugs and logic errors
- Security vulnerabilities
- Performance issues
- Code style violations

$ARGUMENTS.scope changes:
```

### Installation Command
```bash
# Install specific command
ccg setup commands review

# Install all bundled commands
ccg setup commands --all

# List available commands
ccg setup commands --list

# Install to project vs user level
ccg setup commands review --user
ccg setup commands review  # project level (default)
```

## Tasks
- [ ] Define command format specification
- [ ] Create 5-10 initial bundled commands
- [ ] Implement command installation
- [ ] Implement command listing
- [ ] Add command documentation
- [ ] Support project vs user level installation
