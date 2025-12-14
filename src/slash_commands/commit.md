---
description: Generate a conventional commit message for staged changes
arguments:
  - name: type
    description: Commit type (feat, fix, docs, style, refactor, perf, test, build, ci, chore)
    required: false
---

# Generate Commit Message

Analyze the staged changes and generate a conventional commit message.

## Instructions

1. Run `git diff --cached` to see staged changes
2. Run `git diff --cached --stat` for a summary
3. Analyze what was changed and why

## Commit Format

Follow the Conventional Commits specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type Selection
${{#if ARGUMENTS.type}}
Use the specified type: **$ARGUMENTS.type**
${{else}}
Determine the most appropriate type:
- **feat**: New feature or functionality
- **fix**: Bug fix
- **docs**: Documentation only
- **style**: Formatting, no code change
- **refactor**: Code change without feature/fix
- **perf**: Performance improvement
- **test**: Adding/correcting tests
- **build**: Build system or dependencies
- **ci**: CI configuration
- **chore**: Other maintenance
${{/if}}

### Guidelines

1. **Subject line**
   - Imperative mood: "add" not "added"
   - Lowercase after type
   - No period at end
   - Max 50 chars (72 limit)

2. **Scope** (optional)
   - Module or component affected
   - Keep it short

3. **Body** (if needed)
   - Explain what and why
   - Wrap at 72 chars

4. **Footer** (if needed)
   - Issue references: "Fixes #123"
   - Breaking changes: "BREAKING CHANGE: ..."

## Output

Provide the commit message ready to use:

```
<the complete commit message>
```

Then ask if the user wants to commit with this message.
