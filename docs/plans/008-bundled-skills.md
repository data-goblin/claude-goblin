# 008: Bundled Skills for Claude Code

## Summary
Include useful skills that enhance Claude Code workflows, installable via `ccg setup skills`.

## Candidate Skills

### Code Quality Skills
- **test-generator**: Generate unit tests for functions/classes
- **docstring-writer**: Add/update docstrings
- **refactor-suggester**: Suggest refactoring opportunities

### Project Management Skills
- **changelog-updater**: Update CHANGELOG.md based on commits
- **version-bumper**: Semantic version management
- **dependency-auditor**: Check for outdated/vulnerable deps

### Documentation Skills
- **readme-generator**: Generate/update README sections
- **api-documenter**: Generate API documentation
- **architecture-diagrammer**: Create architecture diagrams

### Workflow Skills
- **pr-preparer**: Prepare PR description from changes
- **commit-message-writer**: Generate conventional commits
- **issue-creator**: Create issues from TODOs

## Implementation

### Skill Format
```
~/.claude/skills/
  test-generator/
    skill.md           # Skill definition
    templates/         # Optional templates
    examples/          # Usage examples
```

### Installation Command
```bash
# Install specific skill
ccg setup skills test-generator

# Install all bundled skills
ccg setup skills --all

# List available skills
ccg setup skills --list
```

### Skill Definition (skill.md)
```markdown
# Test Generator Skill

## Description
Generates unit tests for Python functions and classes.

## Triggers
- When user asks to "write tests for..."
- When user asks to "add test coverage..."

## Instructions
1. Analyze the target code
2. Identify edge cases
3. Generate pytest-compatible tests
...
```

## Tasks
- [ ] Define skill format specification
- [ ] Create 3-5 initial bundled skills
- [ ] Implement skill installation command
- [ ] Implement skill listing
- [ ] Add skill documentation
- [ ] Create skill templates
