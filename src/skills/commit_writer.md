# Commit Message Writer

Write clear, conventional commit messages that follow best practices.

## When to Use

Activate this skill when:
- User asks to "write a commit message"
- User asks to "commit these changes"
- User wants help with git commit formatting
- After completing a feature or fix

## Commit Message Format

Follow the Conventional Commits specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature or functionality
- **fix**: Bug fix
- **docs**: Documentation only changes
- **style**: Code style changes (formatting, semicolons, etc.)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvement
- **test**: Adding or correcting tests
- **build**: Changes to build system or dependencies
- **ci**: CI configuration changes
- **chore**: Other changes that don't modify src or test files

### Rules

1. **Subject line**
   - Use imperative mood: "Add feature" not "Added feature"
   - Don't capitalize first letter after type
   - No period at the end
   - Max 50 characters (72 hard limit)

2. **Body** (optional)
   - Separate from subject with blank line
   - Wrap at 72 characters
   - Explain what and why, not how

3. **Footer** (optional)
   - Reference issues: "Fixes #123"
   - Breaking changes: "BREAKING CHANGE: description"

## Examples

### Simple fix
```
fix(auth): prevent race condition in token refresh
```

### Feature with body
```
feat(dashboard): add activity heatmap visualization

Display GitHub-style contribution graph showing daily token usage.
Includes streak tracking and fun statistics like "Office episodes"
comparison.
```

### Breaking change
```
feat(api)!: change response format to JSON:API spec

BREAKING CHANGE: API responses now follow JSON:API specification.
All clients must update their response parsing logic.

Closes #456
```

### Multiple changes
```
refactor(storage): simplify database connection handling

- Extract connection logic to dedicated module
- Add connection pooling support
- Remove deprecated sync methods

Part of the v2.0 architecture improvements.
```

## Best Practices

- One logical change per commit
- Write for future readers (including yourself)
- Reference related issues or PRs
- Don't commit secrets or sensitive data
- Verify changes compile/pass tests before committing
