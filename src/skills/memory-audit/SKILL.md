---
name: memory-audit
description: Self-audit Claude Code memory files. Triggers on repeated corrections, failed-then-succeeded patterns, explicit "remember this" signals, or requests to review memory. Learns what matters for the project through conversation.
---

# Memory Audit Skill

Learn what matters. Capture lessons from failures and repetition. Keep it concise.


## When to Trigger

### Automatic Triggers

- **Repeated corrections** — User corrects same thing twice → ask if it should be remembered
- **Failed then succeeded** — Approach failed, different one worked → capture what worked
- **Explicit signals** — "remember this", "always do X", "never do Y", "next time..."
- **Style friction** — User reformats output or adjusts tone → ask about preferences
- **Workflow discovery** — User shares command or process not in memory

### Manual Triggers

- User asks to review memory
- Starting on unfamiliar project
- After significant project changes


## Core Approach

Ask the user:

> "What's important for me to remember about this project?"

Let them define what matters. Don't assume categories.


## Learning from Failure

When something fails then succeeds:

1. Note what failed and why
2. Note what worked
3. Propose: "Should I remember to [what worked] for [this type of task]?"
4. If yes, suggest one-line addition

Example:
> "I tried pandas but this project uses polars. Add 'Use polars, not pandas' to memory?"


## Learning from Repetition

When patterns emerge:

- User corrects formatting twice → "You prefer [X]. Add to memory?"
- User provides same context repeatedly → "Should I remember [context]?"
- User runs same command first → "Note as standard workflow?"

One suggestion at a time. Keep it brief.


## Suggesting Additions

When proposing memory entries:

1. Quote what triggered the suggestion
2. Propose minimal addition (one line if possible)
3. Name the target file
4. Ask confirmation

Example:
> You said "always use composition over inheritance." Add to `.claude/rules/style.md`?
> ```
> - Prefer composition over inheritance
> ```


## Conciseness

Memory entries should be:

- **One line when possible** — "2-space indent" not a paragraph
- **Actionable** — "Run `npm test` before commits" not "testing matters"
- **Specific** — "camelCase variables" not "good naming"

Bad:
```markdown
## Code Style Guidelines
When writing code, please ensure you follow our conventions...
```

Good:
```markdown
- 2-space indent, no tabs
- camelCase variables, PascalCase components
```


## File Structure

### Preferred: `.claude/rules/`

```
.claude/
├── CLAUDE.md        # Entry, imports rules
└── rules/
    ├── style.md     # Code and output style
    ├── project.md   # Project-specific knowledge
    └── workflows.md # Commands and processes
```

### File Purposes

| File | Use |
|------|-----|
| `.claude/rules/*.md` | Shared team knowledge |
| `CLAUDE.local.md` | Personal deviations from team standards |
| `~/.claude/CLAUDE.md` | Cross-project preferences |


## Running an Audit

Use `scripts/audit_memory.py <project-path>` to:

- Discover existing memory files
- Check for vague instructions ("follow best practices" → ask for specifics)
- Detect scope issues (personal prefs in shared files)
- Identify missing coverage
- Validate imports resolve

Then ask the user what else matters.
