# Commands Reference

Complete reference for all `claude-goblin` commands.

## Commands

### Dashboard & Analytics

#### `claude-goblin usage`
Show usage dashboard with KPI cards and breakdowns.

Displays:
- Total tokens, prompts, and sessions
- Current usage limits (session, weekly, Opus)
- Token breakdown by model
- Token breakdown by project

#### `claude-goblin limits`
Show current usage limits (session, week, Opus).

Displays current usage percentages and reset times for all three limit types.

**Note:** Must be run from a trusted folder where Claude Code has been used.

#### `claude-goblin stats`
Show detailed statistics and cost analysis.

Displays:
- Summary: total tokens, prompts, responses, sessions, days tracked
- Cost analysis: estimated API costs vs Max Plan costs
- Averages: tokens per session/response, cost per session/response
- Text analysis: prompt length, politeness markers, phrase counts
- Usage by model: token distribution across different models

#### `claude-goblin status-bar <type>`
Launch macOS menu bar app (macOS only).

Shows "CC: XX%" in your menu bar with auto-refresh every 5 minutes.

**Arguments:**
- `type` - Type of limit to display: `session`, `weekly`, or `opus` (default: `weekly`)

### Export

#### `claude-goblin export`
Export yearly heatmap as PNG or SVG.

Generates a GitHub-style activity heatmap showing Claude Code usage throughout the year.

### Data Management

#### `claude-goblin update-usage`
Update historical database with latest data.

This command:
1. Saves current usage data from JSONL files
2. Fills in missing days with zero-usage records
3. Ensures complete date coverage from earliest record to today

Useful for ensuring continuous heatmap data without gaps.

#### `claude-goblin delete-usage`
Delete historical usage database.

**WARNING:** This will permanently delete all historical usage data!

A backup is automatically created before deletion.

#### `claude-goblin restore-backup`
Restore database from backup file.

Restores the usage history database from `~/.claude/usage/usage_history.db.bak`.
Creates a safety backup of the current database before restoring.

### Cross-Device Sync

#### `ccg sync setup`
Configure cross-device sync for usage data.

Interactive wizard that guides through:
1. Storage format selection (SQLite or DuckDB)
2. Sync provider selection (Syncthing, OneDrive, OneLake, MotherDuck, or None)

**Flags:**
- `--storage, -s` - Storage format: `sqlite` or `duckdb`
- `--provider, -p` - Sync provider: `syncthing`, `onedrive`, `onelake`, `motherduck`, `none`
- `--device-id, -d` - Device identifier (auto-generated if not provided)
- `--device-name, -n` - Human-readable device name (hostname if not provided)
- `--yes, -y` - Auto-confirm all prompts (for non-interactive use)
- `--install` - Auto-install missing dependencies (requires `--yes`)
- `--workspace, -w` - OneLake workspace name (for OneLake provider)
- `--lakehouse, -l` - OneLake lakehouse name (for OneLake provider)
- `--token, -t` - MotherDuck token (for MotherDuck provider)
- `--onedrive-path` - OneDrive folder path (for OneDrive provider)

#### `ccg sync status`
Show current sync configuration and status.

Displays:
- Storage format and database path
- Sync provider and configuration
- Device information (ID, name, type)
- Provider-specific status (connection state, peers, etc.)

#### `ccg sync add-device <device-id>`
Add a remote device for Syncthing sync.

**Arguments:**
- `<device-id>` - Syncthing device ID of the peer to add

**Note:** Only available when using Syncthing provider.

### Hooks (Advanced)

#### `claude-goblin setup-hooks <type>`
Setup Claude Code hooks for automation.

**Arguments:**
- `type` - Hook type to setup: `usage`, `audio`, or `png`

Hook types:
- `usage` - Auto-track usage after each Claude response
- `audio` - Play sounds for completion and permission requests
- `png` - Auto-update usage PNG after each Claude response

#### `claude-goblin remove-hooks [type]`
Remove Claude Code hooks configured by this tool.

**Arguments:**
- `type` (optional) - Hook type to remove: `usage`, `audio`, `png`, or omit to remove all

## Flags & Arguments

### Global Flags

None currently available.

### Command-Specific Flags

#### `usage` command
- `--live` - Auto-refresh dashboard every 5 seconds
- `--fast` - Skip live limits for faster rendering

#### `export` command
- `--svg` - Export as SVG instead of PNG
- `--open` - Open file after export
- `-y, --year <YYYY>` - Filter by year (default: current year)
- `-o, --output <path>` - Output file path

#### `delete-usage` command
- `-f, --force` - Force deletion without confirmation (required)

#### `status-bar` command
Arguments:
- `<type>` - Limit type: `session`, `weekly`, or `opus` (default: `weekly`)

#### `setup-hooks` command
Arguments:
- `<type>` - Hook type: `usage`, `audio`, or `png` (required)

#### `remove-hooks` command
Arguments:
- `[type]` - Hook type to remove: `usage`, `audio`, `png`, or omit for all (optional)

## Examples

```bash
# View dashboard
claude-goblin usage

# View dashboard with auto-refresh
claude-goblin usage --live

# Export current year as PNG and open it
claude-goblin export --open

# Export specific year
claude-goblin export -y 2024

# Export as SVG to specific path
claude-goblin export --svg -o ~/reports/usage.svg

# Show current limits
claude-goblin limits

# Launch menu bar with weekly usage
claude-goblin status-bar weekly

# Setup automatic usage tracking
claude-goblin setup-hooks usage

# Setup audio notifications
claude-goblin setup-hooks audio

# Remove all hooks
claude-goblin remove-hooks

# Remove only audio hooks
claude-goblin remove-hooks audio

# Delete all historical data (with confirmation)
claude-goblin delete-usage --force

# Configure sync with Syncthing (interactive)
ccg sync setup

# Configure sync with SQLite + Syncthing (non-interactive)
ccg sync setup --storage sqlite --provider syncthing --device-id mac-work --yes

# Configure sync with DuckDB + MotherDuck
ccg sync setup --storage duckdb --provider motherduck --token md_xxx --yes

# Configure sync with OneLake
ccg sync setup --provider onelake --workspace "Analytics" --lakehouse "Usage" --yes

# Check sync status
ccg sync status

# Add Syncthing peer device
ccg sync add-device ABCD-1234-WXYZ-5678
```

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| **JSONL logs** | `~/.claude/projects/*.jsonl` | Current 30-day usage data from Claude Code |
| **SQLite DB (legacy)** | `~/.claude/usage/usage_history.db` | Historical usage data (no sync) |
| **SQLite DB (per-device)** | `~/.claude/usage/{device_id}.db` | Per-device database for sync |
| **DuckDB (per-device)** | `~/.claude/usage/{device_id}.duckdb` | DuckDB database for sync |
| **DB Backup** | `~/.claude/usage/usage_history.*.bak` | Automatic backup before destructive operations |
| **Default exports** | `~/.claude/usage/claude-usage.png` | PNG/SVG heatmaps |
| **Settings** | `~/.claude/settings.json` | Claude Code settings including hooks configuration |
| **Goblin config** | `~/.claude/goblin_config.json` | Claude Goblin settings (storage, sync, device info) |
