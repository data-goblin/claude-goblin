# Memory Examples

## Good Memory Entries

Concise, actionable, specific:

```markdown
# Style
- 2-space indent, no tabs
- camelCase variables, PascalCase components
- Imports: external → internal → relative

# Tone
- Concise responses, expand only when asked
- No emoji
- British English

# Workflows
- Build: `npm run build`
- Test: `npm test`
- Lint: `npm run lint`

# Project
- Use polars, not pandas
- State in Zustand, not Redux
- API routes in src/api/
```


## Bad Memory Entries

Vague, verbose, or obvious:

```markdown
# Don't do this
- Follow best practices
- Write clean code
- Be consistent with the codebase
- Use appropriate naming conventions

# Or this
## Code Style Guidelines
When writing code for this project, you should ensure that
all formatting follows our established conventions. This includes
proper indentation, meaningful variable names, and...
```


## Capturing Lessons

After failure → success:

```markdown
# Learned
- Don't use `any` — this project has strict TypeScript
- Run `pnpm install` not `npm install` (monorepo)
- Tests need `--experimental-vm-modules` flag
```

After repeated corrections:

```markdown
# Preferences
- No bullet points in explanations
- Ask before generating code
- Prefer prose over structured output
```


## File Scope

| Where | What |
|-------|------|
| `.claude/rules/` | Team knowledge, versioned |
| `CLAUDE.local.md` | Deviate from team without affecting others |
| `~/.claude/CLAUDE.md` | Personal defaults across all projects |


## Import Syntax

```markdown
@.claude/rules/style.md      # Relative to project
@~/my-defaults.md            # Home directory
```

Max depth: 5 imports deep.


