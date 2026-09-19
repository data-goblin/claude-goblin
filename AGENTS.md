# Claude Goblin Usage - Project Memory

## Project Overview

A Python-based utilities CLI for Claude Code that provides tools and analytics to extend Claude Code's capabilities. Designed to be safe, efficient, and extensible, offering features like usage analytics, success metrics, and productivity insights.

- Ensure that whenever you create a new version that you update /docs/versions with a markdown file for that version.

## Project Structure

```yaml
claude-goblin-usage/
├── src/
│   └── claude_goblin_usage/
│       ├── __init__.py
│       ├── cli.py                    # CLI entry point
│       ├── config/                   # Configuration management
│       │   ├── __init__.py
│       │   └── settings.py           # App settings and constants
│       ├── data/                     # Data access layer
│       │   ├── __init__.py
│       │   └── jsonl_parser.py       # JSONL log file parser
│       ├── models/                   # Data models
│       │   ├── __init__.py
│       │   └── usage_record.py       # Usage data models
│       ├── aggregation/              # Data aggregation logic
│       │   ├── __init__.py
│       │   └── daily_stats.py        # Daily statistics aggregator
│       └── visualization/            # UI/Display layer
│           ├── __init__.py
│           └── activity_graph.py     # GitHub-style activity graph
├── tests/                            # Test suite
├── pyproject.toml                    # Project configuration
└── README.md                         # Project documentation
```

## Architecture Principles

- **Safety First**: Read-only operations on Claude Code data, no modifications to user files
- **Separation of Concerns**: Each module has a single, well-defined responsibility
- **Data Flow**: data → models → aggregation → visualization
- **Type Safety**: Using mypy with strict typing
- **Testability**: All modules are independently testable
- **Extensibility**: Plugin-based architecture for adding new utilities and metrics

## Core Components

### 1. Data Layer (`data/`)

- Parses JSONL files from `~/.claude/data/`
- Extracts raw usage events
- No business logic - pure data access

### 2. Models Layer (`models/`)

- Defines data structures
- Usage records, session info, token counts
- Immutable data classes

### 3. Aggregation Layer (`aggregation/`)

- Transforms raw data into daily statistics
- Groups by date, model, folder, version
- Calculates totals and metrics

### 4. Visualization Layer (`visualization/`)

- GitHub-style activity graph rendering
- Real-time dashboard updates
- Rich terminal UI

### 5. Config Layer (`config/`)

- Application settings
- Constants and configuration
- Environment-based settings

## Dependencies

- `rich`: Terminal UI rendering
- Python 3.10+
- `uv`: Package management

## Development Notes
- Always use python3 explicitly (Mac requirement)
- Follow #region organization in all files
- Document all functions with purpose, inputs, outputs, failure modes
- Run tests incrementally during development
- No placeholder code - only complete implementations
- **NEVER commit or push without explicit user approval** - always wait for user to test and explicitly request commit/push

## Git Best Practices
- **Commit regularly**: Make small, focused commits after completing each logical unit of work
- **Push frequently**: Push changes to remote after each commit or group of related commits to avoid losing work
- **Use descriptive commit messages**: Follow conventional commits format (feat:, fix:, docs:, refactor:, etc.)
- **Don't let changes pile up**: Large uncommitted changesets are hard to review and easy to lose
- **Branch appropriately**: Use feature branches (like v0.2.0dev) for development work, keep main/master stable

## Release Process

When releasing a new version:

1. **Update CHANGELOG.md**
   - Add new version section at the top with date
   - List changes under Added/Changed/Fixed sections
   - Keep descriptions brief and user-focused

2. **Update pyproject.toml**
   - Bump version number (e.g., `0.1.4` → `0.1.5`)

3. **Update README.md** (if needed)
   - Add new flags or commands to the command table
   - Keep changes minimal, only add what's actually new

4. **Commit changes in logical groups**
   - Fix/Feature commits first (e.g., "Fix: Add limits tracking to stats command")
   - Cleanup commits second (e.g., "Clean: Update command references")
   - Version bump commit last (e.g., "Release: Version 0.1.5")

5. **Tag and push**

   ```bash
   git push origin master
   git tag -a v0.1.5 -m "Release v0.1.5"
   git push origin v0.1.5
   ```

6. **Build and publish to PyPI**

   ```bash
   python3 -m build
   python3 -m twine upload dist/claude_goblin-0.1.5*
   ```

## Testing Strategy

- Unit tests for each module
- Integration tests for data pipeline
- Validate edge cases (missing files, corrupted JSONL, empty data)
- Test with real Claude data

## Known Issues / Decisions

- `claude-goblin limits`: Cannot automatically handle Claude's folder trust prompt. Must be run from a trusted folder (where Claude Code has been used before) or after establishing trust manually with `claude` command
- **CRITICAL BUG FIXED (2025-10-11)**: In "full" storage mode, the old code used `INSERT OR REPLACE` which would recalculate ALL daily_snapshots from current usage_records. This caused data loss when JSONL files aged out (30-day window). Fixed to only update dates that currently have records, preserving historical daily_snapshots forever.
- **NEVER test `delete-usage --force` on production database** - it permanently deletes ALL historical data with no recovery

## Next Steps

1. Implement JSONL parser for Claude Code data
2. Create data models for usage records
3. Build aggregation logic for daily statistics
4. Create activity graph visualization (GitHub-style)
5. Add auto-refresh dashboard mechanism
6. Implement success metrics (completion rates, error tracking)
7. Add cost tracking utilities
8. Integrate with Claude Code hooks for real-time updates
9. Build export functionality for reports
10. Create extensible plugin system for custom utilities

- Don't use PYTHONPATH just install and use the CLI directly if you need to test it.
- When you make changes to the database that modifies schema delete it first otherwise youll get errors