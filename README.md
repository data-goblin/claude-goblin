# Claude Code Goblin

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![Claude Code](https://img.shields.io/badge/Claude%20Code-required-orange?logo=anthropic)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

Python command line tool to help with Claude Code utilities and Claude Code usage analytics and long-term tracking.


**Quick Start:** Install with `pip install claude-goblin` and use `ccg --help` for commands or `ccg usage` to start tracking. Below are some examples of outputs that this command line can give you.

> [!NOTE]
> Both `claude-goblin` and `ccg` work interchangeably as command aliases.

## Example outputs

**TUI Dashboard:**

![Example TUI dashboard](docs/images/dashboard.png)

---

**MacOS status bar for usage limits:**

![Example status bar](docs/images/status-bar.png)

---

**GitHub activity-style heatmap of annual usage:**

![Example heatmap](docs/images/heatmap.png)

--- 


> [!NOTE] 
> This tool was developed and tested on macOS (Python 3.13). Should work on Linux and Windows but is untested on those platforms.



## Features

- Local snapshotting of Claude Code logs for analytics
- Local snapshotting of usage limits from the Claude Code `/usage` command
- Dashboard and stats of usage and limit history
- Project anonymization for sharing screenshots (`--anon` flag)
- Hook setup to automate data logging or analysis of Claude Code
- Audio notifications for Claude Code completion, permission requests, and conversation compaction
- Text-to-speech (TTS) notifications with customizable hook selection (macOS only)

## Installation

### From PyPI (recommended)
```bash
# Install from PyPI
pip install claude-goblin

# Optional: Install export dependencies for PNG/SVG generation
pip install "claude-goblin[export]"
```

### From source
```bash
# Clone the repository
git clone https://github.com/data-goblin/claude-goblin.git
cd claude-goblin

# Install with pip
pip install -e .

# Optional: Install export dependencies
pip install -e ".[export]"
```

## First-Time Setup

After installation, start tracking your Claude Code usage:

```bash
# View your current usage dashboard
ccg usage

# (Optional) Enable automatic tracking with hooks
ccg setup-hooks usage
```

**Note**: The `usage` command automatically saves your data to the historical database every time you run it. No manual setup required.

### Commands Explained

- **`update-usage`**: Update historical database with latest data and fill in missing date gaps with empty records (use when you want continuous date coverage for the heatmap)

For most users, just run `usage` regularly and it will handle data tracking automatically. Use `setup-hooks usage` to automate this completely.

## Commands

| Command | Description |
|---------|-------------|
| **Dashboard & Analytics** | |
| `ccg usage` | Show usage dashboard with KPI cards and breakdowns |
| `ccg usage --live` | Auto-refresh dashboard every 5 seconds |
| `ccg usage --fast` | Skip live limits for faster rendering |
| `ccg usage --anon` | Anonymize project names (project-001, project-002, etc.) |
| `ccg limits` | Show current usage limits (session, week, Opus) |
| `ccg stats` | Show detailed statistics and cost analysis |
| `ccg stats --fast` | Skip live limits for faster rendering |
| `ccg status-bar [type]` | Launch macOS menu bar app (session\|weekly\|opus) |
| **Export** | |
| `ccg export` | Export yearly heatmap as PNG (default) |
| `ccg export --svg` | Export as SVG image |
| `ccg export --open` | Export and open the image |
| `ccg export -y 2024` | Export specific year |
| `ccg export -o output.png` | Specify output file path |
| **Data Management** | |
| `ccg update-usage` | Update historical database with latest data |
| `ccg delete-usage --force` | Delete historical database (requires --force) |
| `ccg restore-backup` | Restore from backup |
| **Hooks (Advanced)** | |
| `ccg setup-hooks usage` | Auto-track usage after each Claude response |
| `ccg setup-hooks audio` | Play sounds for completion, permission & compaction |
| `ccg setup-hooks audio-tts` | Speak notifications using TTS (macOS, multi-hook) |
| `ccg setup-hooks png` | Auto-generate PNG after each response |
| **Awesome-hooks (PreToolUse)** | |
| `ccg setup-hooks uv-standard` | Enforce uv instead of pip/pip3 |
| `ccg setup-hooks bundler-standard` | Enforce Bun instead of npm/pnpm/yarn |
| `ccg setup-hooks file-name-consistency` | Ensure consistent file naming |
| `ccg remove-hooks [type]` | Remove hooks (any hook type, or all) |

## Data Source

Claude Goblin reads usage data from Claude Code's local session logs:
```
~/.claude/projects/*.jsonl
```

**Important**: Claude Code retains session logs for approximately **30 days** (rolling window). There is no way to get other historical data without contacting Anthropic support. Claude Goblin solves this by:
- Automatically saving data to an SQLite database (`~/.claude/usage/usage_history.db`) whenever you run `--usage`
- Preserving historical data indefinitely
- Merging current + historical data for complete analytics
- Configuration to choose between saving detailed or aggregate data

## How It Works

```mermaid
graph TD
    A[Claude Code] -->|writes| B[JSONL Files<br/>~/.claude/projects/*.jsonl]
    A -.->|triggers| H[Hooks]

    B --> ING{Ingestion<br/>--usage<br/>--update-usage}
    H -.->|automates| ING

    ING --> DB[(Database<br/>~/.claude/usage/usage_history.db)]

    DB --> CMD1{--usage}
    DB --> CMD2{--stats}
    DB --> CMD3{--export}

    CMD1 --> OUT1[TUI Dashboard]
    CMD2 --> OUT2[Summary Stats<br/>in Terminal]
    CMD3 --> OUT3[Annual Activity PNG]

    H -.->|automates| CMD3

    style A fill:#e0e0e0,stroke:#333,color:#000
    style B fill:#ff8800,stroke:#333,color:#000
    style DB fill:#4a9eff,stroke:#333,color:#fff
    style OUT1 fill:#90ee90,stroke:#333,color:#000
    style OUT2 fill:#90ee90,stroke:#333,color:#000
    style OUT3 fill:#90ee90,stroke:#333,color:#000
    style H fill:#ffeb3b,stroke:#333,color:#000
```

**Key Points:**
- **JSONL files** are raw logs with a 30-day rolling window (older data disappears)
- **Ingestion** step reads JSONL and saves to DB (with automatic deduplication via `UNIQUE` constraint)
- **Database** is the single source of truth - all display commands read from here only
- **Hooks** can automate ingestion after each Claude response

### Command Behavior

**`ccg usage`** (Display + Ingestion)
1. **Ingestion**: Reads JSONL files from `~/.claude/projects/*.jsonl` and saves to DB
2. **Display**: Reads data from DB and renders dashboard

**`ccg export`** (Display only)
1. Reads data from DB at `~/.claude/usage/usage_history.db`
2. Generates yearly heatmap
3. Exports to current directory as `claude-usage-<timestamp>.png` (or specify with `-o`)

**`ccg stats`** (Display + Ingestion)
1. **Ingestion**: Reads JSONL files from `~/.claude/projects/*.jsonl` and saves to DB
2. **Display**: Reads data from DB and displays comprehensive statistics

**`ccg update-usage`** (Ingestion only)
1. Reads JSONL files from `~/.claude/projects/*.jsonl`
2. Saves to DB at `~/.claude/usage/usage_history.db` (with automatic deduplication)
3. Fills in missing dates with empty records (ensures continuous heatmap)

### File Locations

| File | Location | Purpose |
|------|----------|---------|
| **JSONL logs** | `~/.claude/projects/*.jsonl` | Current 30-day usage data from Claude Code |
| **SQLite DB** | `~/.claude/usage/usage_history.db` | Historical usage data preserved indefinitely |
| **Default exports** | `~/.claude/usage/claude-usage-<timestamp>.png` | PNG/SVG heatmaps (default location unless `-o` is used) |
| **Hook exports** | `~/.claude/usage/claude-usage.png` | Default location for PNG hook auto-updates |

## --usage TUI dashboard

Example TUI:

![Example TUI dashboard](docs/images/dashboard.png)

## --export Heatmap

Export a GitHub-style yearly activity heatmap:

```bash
ccg export --open
```

Example heatmap:

![Yearly activity heatmap](docs/images/heatmap.png)

### --export Formats

- **PNG** (default): `ccg export`

## --status-bar (macOS only)

Launch a menu bar app showing your Claude Code usage limits:

```bash
# Show weekly usage (default)
ccg status-bar weekly

# Show session usage
ccg status-bar session

# Show Opus weekly usage
ccg status-bar opus
```

The menu bar displays "CC: XX%" and clicking it shows all three limits (Session, Weekly, Opus) with reset times.

**Running in background:**
- Use `&` to run in background: `ccg status-bar weekly &`
- Use `nohup` to persist after terminal closes: `nohup ccg status-bar weekly > /dev/null 2>&1 &`

Example:

![example status bar](docs/images/status-bar.png)

## Hooks

Claude Goblin can integrate with Claude Code's hook system to automate various tasks. Hooks trigger automatically based on Claude Code events.

### Claude Goblin Hook Types

#### Usage Hook
Automatically tracks usage data after each Claude response:
```bash
ccg setup-hooks usage
```

This adds a hook that runs `ccg update-usage --fast` after each Claude response, keeping your historical database up-to-date.

#### Audio Hook
Plays system sounds for three different events:
```bash
ccg setup-hooks audio
```

You'll be prompted to select three sounds:
1. **Completion sound**: Plays when Claude finishes responding
2. **Permission sound**: Plays when Claude requests permission
3. **Compaction sound**: Plays before conversation compaction

Supports macOS (10 built-in sounds), Windows, and Linux.

#### Audio TTS Hook (macOS only)
Speaks notifications aloud using macOS text-to-speech:
```bash
ccg setup-hooks audio-tts
```

**Multi-hook selection** - Choose which events to speak:
1. Notification only (permission requests) - **[recommended]**
2. Stop only (when Claude finishes responding)
3. PreCompact only (before conversation compaction)
4. Notification + Stop
5. Notification + PreCompact
6. Stop + PreCompact
7. All three (Notification + Stop + PreCompact)

You can also select from 7 different voices (Samantha, Alex, Daniel, Karen, Moira, Fred, Zarvox).

**Example messages:**
- Notification: Speaks the permission request message
- Stop: "Claude finished responding"
- PreCompact: "Auto compacting conversation" or "Manually compacting conversation"

#### PNG Hook
Auto-generates usage heatmap PNG after each Claude response:
```bash
ccg setup-hooks png
```

Requires export dependencies: `pip install "claude-goblin[export]"`

### Awesome-hooks (PreToolUse)

Claude Goblin includes PreToolUse hooks from [awesome-hooks](https://github.com/boxabirds/awesome-hooks) by [@boxabirds](https://github.com/boxabirds), plus a custom Python/uv enforcement hook. These hooks intercept and validate commands before they execute.

#### uv-standard Hook
Enforces uv usage instead of pip/pip3:
```bash
ccg setup-hooks uv-standard
```

**What it does:**
- Intercepts pip/pip3 commands in Bash
- Blocks them and suggests uv equivalents
- Ensures you use uv for Python package management

**Requirements:** uv package installer ([installation](https://github.com/astral-sh/uv))

#### bundler-standard Hook
Enforces Bun usage instead of npm/pnpm/yarn:
```bash
ccg setup-hooks bundler-standard
```

**What it does:**
- Intercepts npm/pnpm/yarn commands in Bash
- Blocks them and suggests Bun equivalents
- Ensures you use Bun for JavaScript package management

**Requirements:** Bun runtime ([installation](https://bun.sh))

#### file-name-consistency Hook
Ensures consistent file naming conventions:
```bash
ccg setup-hooks file-name-consistency
```

**What it does:**
- Analyzes your project's file naming patterns using AI
- Blocks files with inconsistent naming
- Suggests correctly formatted filenames

**Requirements:** GEMINI_API_KEY environment variable ([get your key](https://aistudio.google.com/apikey))

Set the API key in your shell profile:
```bash
export GEMINI_API_KEY="your-api-key-here"
```

### Removing Hooks

```bash
# Remove specific hook type
ccg remove-hooks usage
ccg remove-hooks audio
ccg remove-hooks audio-tts
ccg remove-hooks png
ccg remove-hooks uv-standard
ccg remove-hooks bundler-standard
ccg remove-hooks file-name-consistency

# Remove all Claude Goblin hooks
ccg remove-hooks
```

## Project Anonymization

The `--anon` flag anonymizes project names when displaying usage data, perfect for sharing screenshots:

```bash
ccg usage --anon
ccg stats --anon
```

Projects are renamed to `project-001`, `project-002`, etc., ranked by total token usage (project-001 has the highest usage).

## Historical Data

Claude Goblin automatically saves data every time you run `usage`. To manually manage:

```bash
# View historical stats
ccg stats

# Update database with latest data and fill date gaps
ccg update-usage

# Delete all history
ccg delete-usage -f
```

## What It Tracks

- **Tokens**: Input, output, cache creation, cache read (by model and project)
- **Prompts**: User prompts and assistant responses
- **Sessions**: Unique conversation threads
- **Models**: Which Claude models you've used (Sonnet, Opus, Haiku)
- **Projects**: Folders/directories where you've used Claude
- **Time**: Daily activity patterns throughout the year
- **Usage Limits**: Real-time session, weekly, and Opus limits

It will also compute how much you would have had to pay if you used API pricing instead of a $200 Max plan.


## Technical Details

### Timezone Handling

All timestamps in Claude Code's JSONL files seem to be stored in **UTC**. Claude Goblin should convert to your **local timezone** when grouping activity by date. This has only been tested with European CET.

### Cache Efficiency

The token breakdown shows cache efficiency. High "Cache Read" percentages (80-90%+) mean Claude Code is effectively reusing context, which:
- Speeds up responses
- Can reduce costs on usage-based plans
- Indicates good context management

## Requirements

- Python >= 3.10
- Claude Code (for generating usage data)
- Rich >= 13.7.0 (terminal UI)
- rumps >= 0.4.0 (macOS menu bar app, macOS only)
- Pillow + CairoSVG (optional, for PNG/SVG export)

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

I don't have much time but I'll review PRs when I can.

## Troubleshooting

### "No Claude Code data found"
- Ensure Claude Code is installed and you've used it at least once
- Check that `~/.claude/projects/` exists and contains `.jsonl` files

### Limits showing "Could not parse usage data"
- Run `claude` in a trusted folder first
- Claude needs folder trust to display usage limits

### Export fails
- Install export dependencies: `pip install -e ".[export]"`
- For PNG: requires Pillow and CairoSVG

### Database errors
- Try deleting and recreating: `ccg delete-usage --force`
- Then run: `ccg usage` to rebuild from current data

## **AI Tools Disclaimer**: 
This project was developed with assistance from Claude Code.

## Credits

Built with:
- [Rich](https://github.com/Textualize/rich) - Terminal UI framework
- [Pillow](https://python-pillow.org/) - Image processing (optional)
- [CairoSVG](https://cairosvg.org/) - SVG to PNG conversion (optional)

Includes hooks from:
- [awesome-hooks](https://github.com/boxabirds/awesome-hooks) by [@boxabirds](https://github.com/boxabirds) - PreToolUse hooks for enforcing development standards

See [docs/attributions.md](docs/attributions.md) for full attribution details.
