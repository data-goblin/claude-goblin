# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-07-23

### Added
- Hermes Agent ingestion through `extra_sources` entries with
  `"format": "hermes"`. Content-free `post_api_request` JSONL events map to
  the existing `usage_records` fact table, preserving the same token, model,
  session, project, branch, and device dimensions used by Claude and Codex
- Per-call Hermes accounting includes uncached input, output, cache-read, and
  cache-write tokens. Provider identity is retained in `version` as
  `hermes:<provider>`, while the model remains query-compatible in `model`

### Security
- The Hermes parser accepts usage metadata only; prompt/response content,
  reasoning text, tool arguments, user identifiers, and credentials are not
  part of the telemetry format

## [1.1.1] - 2026-07-14

### Fixed
- **Windows**: `ccg setup hooks usage|png` wrote POSIX shell syntax
  (`> /dev/null 2>&1 &`) into settings.json, so the hooks failed on every
  fire under cmd.exe; they now write `>NUL` redirection on Windows, and the
  png export path is quoted so home directories with spaces work everywhere
- **Windows**: settings.json, goblin_config.json, bundled skill markdown,
  and generated hook/devcontainer files were read/written with the locale
  encoding (cp1252 on Windows), corrupting or rejecting UTF-8 content;
  all user-file IO is now explicit UTF-8
- awesome-hooks setup on Windows now exits with a clear message instead of
  installing shebang scripts that cmd.exe cannot execute

### Removed
- Dead `activity_graph` module (imported nowhere, broken at import time by
  the same `datetime.date` annotation shadowing fixed in 1.1.0)

## [1.1.0] - 2026-07-14

### Fixed
- **Windows**: the CLI failed to start on Windows with
  `ModuleNotFoundError: No module named 'termios'` because
  `src/commands/limits.py` imported the POSIX-only `pty` module at import
  time and every command pulled it in transitively (#4)
- `ccg export` crashed on startup (`TypeError` evaluating the
  `datetime.date | None` annotations) because the module shadowed the
  `datetime` module with the `datetime` class
- `ccg --version` reported a stale hardcoded version

### Removed
- Limits tracking, which had been non-functional since Claude Code changed
  its `/usage` output format: the `ccg limits` and `ccg status-bar` commands,
  the `/usage` pty scraper, the limits panels in the dashboard, the
  `--show tokens|limits|both` flag on `ccg export` (now always tokens), and
  the `tracking_mode` config key. The `limits_snapshots` table and its sync
  paths are retained so existing local and remote history is preserved

## [1.0.0] - 2026-07-14

### Added
- Codex ingestion: `~/.codex/sessions` rollout files parse as a token source
  alongside Claude Code transcripts, with per-turn identity that survives
  session resumes and forks
- DuckDB storage backend as an alternative to SQLite, selectable per install
- OneLake sync provider: pushes daily aggregates to a Microsoft Fabric
  lakehouse (any tenant/workspace/lakehouse, fully configurable) and
  generates a Direct Lake semantic model for DAX/Power BI queries
  (`ccg sync query`, `scripts/create_semantic_model.py`)
- Quack DuckDB remote sync provider (replaces Syncthing) with a multi-sink
  push loop - every configured provider gets pushed, one failing doesn't
  block the others
- `ccg sync repair` - rebuilds a quack remote's table after a local
  `--rebuild` without losing any other device's rows (full backup taken
  before anything is dropped or recreated)
- `ccg update usage --rebuild` - recomputes local history from surviving
  transcripts when counting logic changes, with a mandatory pre-repair
  backup and no bare deletes
- Interactive TUI (Textual) and a redesigned dashboard
- Extra sources: ingest external JSONL trees (e.g. a second machine's
  synced transcripts) with per-source device attribution
- Bundled skills and slash commands
- GitHub Actions CI and an automated PR review workflow

### Fixed
- **Token counting**: identity now keys on the billed API response
  (`message.id` + `requestId`), deduplicated globally across sessions.
  Previously every streaming-flush JSONL entry counted separately and
  session forks replayed history into new counts, inflating totals well
  beyond what the API actually billed
- **Pricing**: rates now match what Anthropic/OpenAI/Google actually charge,
  including the 5-minute vs 1-hour prompt-cache-write tiers (1.25x / 2x base
  input) instead of a single flat cache-write rate
- Codex turn identity was scoped per-file, so the cross-session dedupe
  collapsed turns from different sessions onto each other
- Aggregate storage mode no longer re-adds a whole transcript file's totals
  on every reparse - only the delta since the file's last contribution

### Changed
- Nested per-provider sync configuration (`sync_providers`, per-provider
  blocks) replaces the old flat single-provider config
- CLI restructured; see prior 0.1.10 entry for the subcommand renames this
  release builds on

## [0.2.0] - 2025-12-14

### Added
- Cross-device sync support with new `ccg sync` command group
  - `ccg sync setup` - Interactive wizard or non-interactive with flags
  - `ccg sync status` - Show current sync configuration
  - `ccg sync add-device` - Add Syncthing peer device
- Four sync providers:
  - Syncthing (P2P, free, no account)
  - OneDrive (local folder sync)
  - OneLake (Microsoft Fabric lakehouse)
  - MotherDuck (DuckDB cloud, DuckDB storage only)
- DuckDB storage backend as alternative to SQLite
  - Better for analytical queries and large datasets
  - Required for MotherDuck cloud sync
- Per-device database files (`~/.claude/usage/{device_id}.db`) for conflict-free sync
- Device metadata tracking (device_id, device_name, device_type) on all records
- Database migration utilities (SQLite ↔ DuckDB)
- Optional dependencies: `duckdb`, `onelake`, `sync`

### Changed
- Database schema updated to include device metadata columns
- Storage module refactored with `get_db_path()` for dynamic path resolution

## [0.1.10] - 2025-12-14

### Added
- Devcontainer support for safe `--dangerously-skip-permissions` execution
  - Docker container with network firewall (iptables/ipset)
  - Whitelists only essential domains: Anthropic, GitHub, PyPI, npm, MS Learn, MDN
  - New command: `ccg setup container` to initialize devcontainer in any project
- Automatic backup before `remove` operations
  - `ccg remove usage` now creates timestamped backup before deletion
  - `ccg remove hooks` now creates settings.json backup before modification
- `uv.lock` for reproducible builds

### Changed
- **CLI restructured to nested subcommands** for better organization:
  - `ccg setup-hooks` -> `ccg setup hooks`
  - `ccg setup-container` -> `ccg setup container`
  - `ccg remove-hooks` -> `ccg remove hooks`
  - `ccg delete-usage` -> `ccg remove usage`
  - `ccg update-usage` -> `ccg update usage`
  - `ccg restore-backup` -> `ccg restore usage`
- Export command now uses simplified filename (`claude-usage.png` instead of `claude-usage-<timestamp>.png`)

### Deprecated
- **Limits tracking temporarily disabled** due to changes in Claude Code's `/usage` output format
  - `ccg limits` command shows "temporarily unavailable" message
  - `ccg status-bar` command shows "temporarily unavailable" message
  - Dashboard no longer displays live limits (token tracking continues to work)
  - `ccg export --show limits/both` warns that only historical data will be used
  - Run `claude /usage` directly to view your limits
  - This will be fixed in a future release

## [0.1.9] - 2025-10-20

### Added
- Backfilling for missing limits data in PNG exports
  - When there are gaps in opus/weekly limits tracking, missing days are automatically filled with the maximum value from the next earliest day
  - Ensures continuous visualization in activity graphs without gaps

## [0.1.8] - 2025-10-20

### Fixed
- Fixed `ccg limits` and `ccg status-bar` commands failing when Opus usage is at 0%
  - Claude /usage no longer displays reset time for limits at 0%, causing regex parsing to fail
  - Updated parsing logic to handle missing reset times gracefully
- Added Claude Haiku 4.5 pricing ($1/$5 per million input/output tokens)
  - Previously missing model ID `claude-haiku-4-5-20251001` now properly tracked

## [0.1.7] - 2025-10-15

### Fixed
- Fixed `FileNotFoundError` when `claude` CLI is not in PATH - now shows helpful error message instead of traceback
- Improved error handling in `capture_limits()` to gracefully handle missing Claude Code CLI
- Added user-friendly warning when limits tracking fails due to missing `claude` command

## [0.1.6] - 2025-10-15

### Added
- Added awesome-hooks integration from [boxabirds/awesome-hooks](https://github.com/boxabirds/awesome-hooks)
  - `bundler-standard`: Enforce Bun instead of npm/pnpm/yarn (PreToolUse hook)
  - `file-name-consistency`: AI-powered file naming consistency checker (PreToolUse hook, requires GEMINI_API_KEY)
  - `uv-standard`: Custom Python hook to enforce uv instead of pip/pip3 (PreToolUse hook)
- Added `--user` flag to `setup-hooks` and `remove-hooks` commands
  - Default (project-level): Hooks install to `.claude/` in current directory
  - With `--user`: Hooks install to `~/.claude/` for all projects
- Added `docs/attributions.md` with full attribution to awesome-hooks and dependencies

### Changed
- Hook installation now supports two scopes: project-level (default) and user-level (`--user`)
- Project-level hooks install to `.claude/hooks/` in current working directory
- User-level hooks install to `~/.claude/awesome-hooks/` in home directory
- Updated README with comprehensive awesome-hooks documentation and examples
- Hook removal is now scope-aware and only removes intended hooks (preserves custom hooks)

### Technical
- Created `src/hooks/awesome_hooks.py` module for PreToolUse hook management
- Enhanced `uv-standard.py` with robust command detection (handles quotes, comments, sudo, etc.)
- Hooks correctly distinguish between pip execution vs pip as substring/argument
- All 17 edge cases tested and passing for hook robustness

## [0.1.5] - 2025-10-13

### Added
- Added `--fast` flag to `stats` command for faster rendering (skips all updates, reads from database)

### Fixed
- Fixed missing limits updates in `stats` command - now automatically saves limits to database like other commands

## [0.1.4] - 2025-10-12

### Added
- Added `--anon` flag to `usage` command to anonymize project names (displays as project-001, project-002, etc., ranked by token usage)
- Added `PreCompact` hook support for audio notifications (plays sound before conversation compaction)
- Added multi-hook selection for `audio-tts` setup (choose between Notification, Stop, PreCompact, or combinations)
- Audio hook now supports three sounds: completion, permission requests, and conversation compaction

### Changed
- `audio-tts` hook now supports configurable hook types (Notification only by default, with 7 selection options)
- Audio hook setup now prompts for three sounds instead of two (added compaction sound)
- TTS hook script intelligently handles different hook types with appropriate messages
- Enhanced hook removal to properly clean up PreCompact hooks

### Fixed
- Fixed `AttributeError` in `--anon` flag where `total_tokens` was accessed incorrectly on UsageRecord objects

## [0.1.3] - 2025-10-12

### Fixed
- Fixed audio `Notification` hook format to properly trigger on permission requests (removed incorrect `matcher` field)
- Fixed missing limits data in heatmap exports - `usage` command now automatically saves limits to database
- Fixed double `claude` command execution - dashboard now uses cached limits from database instead of fetching live

### Changed
- Improved status messages to show three distinct steps: "Updating usage data", "Updating usage limits", "Preparing dashboard"
- Dashboard now displays limits from database after initial fetch, eliminating redundant API calls

### Added
- Added `get_latest_limits()` function to retrieve most recent limits from database
- Added `--fast` flag to `usage` command for faster dashboard rendering (skips all updates, reads directly from database)
- Added `--fast` flag to `export` command for faster exports (skips all updates, reads directly from database)
- Added database existence check for `--fast` mode with helpful error message
- Added timestamp warning when using `--fast` mode showing last database update date

## [0.1.2] - 2025-10-11

### Added
- Enhanced audio hook to support both `Stop` and `Notification` hooks
  - Completion sound: Plays when Claude finishes responding (`Stop` hook)
  - Permission sound: Plays when Claude requests permission (`Notification` hook)
- User now selects two different sounds during `setup-hooks audio` for better distinction
- Expanded macOS sound library from 5 to 10 sounds

### Changed
- Updated `claude-goblin setup-hooks audio` to prompt for two sounds instead of one
- Audio hook removal now cleans up both `Stop` and `Notification` hooks
- Updated documentation to reflect dual audio notification capability

### Fixed
- Fixed `NameError: name 'fast' is not defined` in usage command when `--fast` flag was used

## [0.1.1] - 2025-10-11

### Fixed
- **CRITICAL**: Fixed data loss bug in "full" storage mode where `daily_snapshots` were being recalculated from scratch, causing historical data to be lost when JSONL files aged out (30-day window)
- Now only updates `daily_snapshots` for dates that currently have records, preserving all historical data forever

### Changed
- Migrated CLI from manual `sys.argv` parsing to `typer` for better UX and automatic help generation
- Updated command syntax: `claude-goblin <command>` instead of `claude-goblin --<command>`
  - Old: `claude-goblin --usage` → New: `claude-goblin usage`
  - Old: `claude-goblin --stats` → New: `claude-goblin stats`
  - Old: `claude-goblin --export` → New: `claude-goblin export`
  - All other commands follow the same pattern
- Updated hooks to use new command syntax (`claude-goblin update-usage` instead of `claude-goblin --update-usage`)
- Improved help messages with examples and better descriptions

### Added
- Added `typer>=0.9.0` as a dependency for CLI framework
- Added backward compatibility in hooks to recognize both old and new command syntax

## [0.1.0] - 2025-10-10

### Added
- Initial release
- Usage tracking and analytics for Claude Code
- GitHub-style activity heatmap visualization
- TUI dashboard with real-time stats
- Cost analysis and API pricing comparison
- Export functionality (PNG/SVG)
- Hook integration for automatic tracking
- macOS menu bar app for usage monitoring
- Support for both "aggregate" and "full" storage modes
- Historical database preservation (SQLite)
- Text analysis (politeness markers, phrase counting)
- Model and project breakdown statistics
