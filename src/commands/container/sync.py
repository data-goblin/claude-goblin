"""
Container sync command for Claude Goblin.

Syncs Claude Code data between container and host.
"""
import json
import os
import shutil
import stat
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Restrictive permissions for sensitive data (owner read/write/execute only)
DIR_PERMISSIONS = stat.S_IRWXU  # 0o700
FILE_PERMISSIONS = stat.S_IRUSR | stat.S_IWUSR  # 0o600


# region Container Detection

def is_in_container() -> bool:
    """Detect if running inside a container."""
    # Check common container indicators
    indicators = [
        os.environ.get("DEVCONTAINER") == "true",
        os.environ.get("REMOTE_CONTAINERS") == "true",
        os.environ.get("KUBERNETES_SERVICE_HOST") is not None,
        os.environ.get("container") == "docker",
        Path("/.dockerenv").exists(),
        Path("/.dockerinit").exists(),
        Path("/run/.containerenv").exists(),
    ]

    # Also check /proc/1/cgroup for container indicators
    try:
        cgroup_path = Path("/proc/1/cgroup")
        if cgroup_path.exists():
            content = cgroup_path.read_text()
            if "docker" in content or "kubepods" in content or "lxc" in content:
                return True
    except (OSError, PermissionError):
        pass

    return any(indicators)


def get_container_type() -> str:
    """Get the type of container we're running in."""
    if os.environ.get("DEVCONTAINER") == "true":
        return "devcontainer"
    if os.environ.get("REMOTE_CONTAINERS") == "true":
        return "vscode-remote"
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return "kubernetes"
    if Path("/.dockerenv").exists() or Path("/.dockerinit").exists():
        return "docker"
    if Path("/run/.containerenv").exists():
        return "podman"
    if os.environ.get("container") == "docker":
        return "docker"
    return "unknown"


def is_path_safe(base_dir: Path, target_path: Path) -> bool:
    """
    Check if target_path is safely contained within base_dir.

    Prevents path traversal attacks via symlinks or .. segments.
    """
    try:
        base_resolved = base_dir.resolve()
        target_resolved = target_path.resolve()
        # Check that resolved target starts with resolved base
        return str(target_resolved).startswith(str(base_resolved) + os.sep) or \
               target_resolved == base_resolved
    except (OSError, ValueError):
        return False


def make_secure_dir(path: Path) -> None:
    """Create directory with restrictive permissions."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(DIR_PERMISSIONS)
    except OSError:
        pass  # May fail on some filesystems


def get_container_claude_dir() -> Path:
    """Get the Claude config directory in the container."""
    # Check CLAUDE_CONFIG_DIR first
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        return Path(config_dir)
    # Fall back to home directory
    return Path.home() / ".claude"


def get_host_sync_dir() -> Path | None:
    """
    Get the host sync directory if mounted.

    Looks for common mount patterns used for host-container sync.
    """
    # Check for explicit sync mount
    sync_mount = os.environ.get("CLAUDE_HOST_SYNC_DIR")
    if sync_mount:
        path = Path(sync_mount)
        if path.exists():
            return path

    # Check for workspace-relative sync directory
    workspace = Path("/workspace")
    if workspace.exists():
        sync_dir = workspace / ".claude-sync"
        if sync_dir.exists():
            return sync_dir

    # Check for home-based sync directory
    home_sync = Path.home() / ".claude-host-sync"
    if home_sync.exists():
        return home_sync

    return None

# endregion


# region Data Sync

def get_jsonl_files(claude_dir: Path) -> list[Path]:
    """Get all JSONL data files from Claude directory."""
    files = []

    # Check data/ directory
    data_dir = claude_dir / "data"
    if data_dir.exists():
        files.extend(data_dir.glob("*.jsonl"))

    # Check root history.jsonl
    history_file = claude_dir / "history.jsonl"
    if history_file.exists():
        files.append(history_file)

    # Check projects directory for session files
    projects_dir = claude_dir / "projects"
    if projects_dir.exists():
        files.extend(projects_dir.glob("**/*.jsonl"))

    return files


def get_projects_data(claude_dir: Path) -> dict:
    """Get project-specific data directories."""
    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return {}

    projects = {}
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir():
            projects[project_dir.name] = {
                "path": project_dir,
                "has_data": (project_dir / "data").exists(),
                "has_memory": (project_dir / "CLAUDE.md").exists(),
            }
    return projects


def sync_jsonl_to_host(container_dir: Path, host_dir: Path, dry_run: bool = False) -> dict:
    """
    Sync JSONL files from container to host directory.

    Returns dict with sync statistics.
    """
    stats = {
        "files_synced": 0,
        "records_synced": 0,
        "records_skipped": 0,
        "files_skipped": 0,
        "errors": [],
    }

    jsonl_files = get_jsonl_files(container_dir)

    if not jsonl_files:
        return stats

    # Resolve base directories for path safety checks
    container_dir_resolved = container_dir.resolve()
    host_dir_resolved = host_dir.resolve()

    for jsonl_file in jsonl_files:
        # Validate source file is within container_dir (prevent symlink attacks)
        if not is_path_safe(container_dir, jsonl_file):
            stats["errors"].append(f"{jsonl_file.name}: path traversal detected, skipped")
            continue

        # Determine target path based on source location
        rel_path = jsonl_file.relative_to(container_dir_resolved)
        host_file = host_dir_resolved / rel_path

        # Validate target file is within host_dir
        if not is_path_safe(host_dir, host_file):
            stats["errors"].append(f"{jsonl_file.name}: target path traversal detected, skipped")
            continue

        if not dry_run:
            make_secure_dir(host_file.parent)

        try:
            # Read container file (handle individual line errors)
            container_records = []
            skipped_lines = 0
            with open(jsonl_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            container_records.append(json.loads(line))
                        except json.JSONDecodeError:
                            skipped_lines += 1

            if skipped_lines > 0:
                stats["records_skipped"] += skipped_lines
                stats["errors"].append(f"{jsonl_file.name}: {skipped_lines} malformed lines skipped")

            if not container_records:
                stats["files_skipped"] += 1
                continue

            if host_file.exists():
                # Merge with existing host file
                host_records = []
                with open(host_file, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            try:
                                host_records.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass  # Skip malformed lines in host file

                # Deduplicate by timestamp + session + uuid (more robust)
                existing_keys = set()
                for r in host_records:
                    # Use uuid if available, fall back to timestamp+session
                    uuid = r.get("uuid", "")
                    ts = r.get("timestamp", "")
                    session = r.get("sessionId", "")
                    key = (uuid, ts, session) if uuid else (ts, session, "")
                    if key != ("", "", ""):  # Skip records with no identifying info
                        existing_keys.add(key)

                new_records = []
                for r in container_records:
                    uuid = r.get("uuid", "")
                    ts = r.get("timestamp", "")
                    session = r.get("sessionId", "")
                    key = (uuid, ts, session) if uuid else (ts, session, "")
                    if key != ("", "", "") and key not in existing_keys:
                        new_records.append(r)
                        existing_keys.add(key)

                if new_records and not dry_run:
                    with open(host_file, "a", encoding="utf-8") as f:
                        for r in new_records:
                            f.write(json.dumps(r, ensure_ascii=False) + "\n")

                stats["records_synced"] += len(new_records)
            else:
                # Copy entire file
                if not dry_run:
                    shutil.copy2(jsonl_file, host_file)
                    # Set restrictive permissions on copied file
                    try:
                        host_file.chmod(FILE_PERMISSIONS)
                    except OSError:
                        pass
                stats["records_synced"] += len(container_records)

            stats["files_synced"] += 1

        except Exception as e:
            stats["errors"].append(f"{jsonl_file.name}: {e}")

    return stats


def sync_ccg_database(container_dir: Path, host_dir: Path, dry_run: bool = False) -> dict:
    """
    Sync ccg usage database from container to host.

    WARNING: This overwrites the host database (with backup).
    Database merge is not yet implemented.

    Returns dict with sync statistics.
    """
    stats = {
        "synced": False,
        "records": 0,
        "error": None,
        "warning": None,
        "backup_path": None,
    }

    # Try both possible database names
    container_db = container_dir / "usage" / "usage_history.db"
    if not container_db.exists():
        container_db = container_dir / "usage" / "usage.db"

    host_usage_dir = host_dir / "usage"
    host_db = host_usage_dir / "usage_history.db"

    if not container_db.exists():
        return stats

    try:
        if not dry_run:
            make_secure_dir(host_usage_dir)

            if host_db.exists():
                # Backup existing host db
                backup_path = host_db.with_suffix(f".backup-{datetime.now().strftime('%Y%m%d%H%M%S')}.db")
                shutil.copy2(host_db, backup_path)
                try:
                    backup_path.chmod(FILE_PERMISSIONS)
                except OSError:
                    pass
                stats["backup_path"] = str(backup_path)
                stats["warning"] = "Host database overwritten (backup created). Database merge not yet implemented."

            # Copy the db (merge logic could be added later)
            shutil.copy2(container_db, host_db)
            try:
                host_db.chmod(FILE_PERMISSIONS)
            except OSError:
                pass

        stats["synced"] = True

    except Exception as e:
        stats["error"] = str(e)

    return stats

# endregion


# region Commands

def status_command():
    """Show container sync status and configuration."""
    console.print()

    # Container detection
    in_container = is_in_container()
    container_type = get_container_type() if in_container else "N/A"

    table = Table(title="Container Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("In Container", "[green]Yes[/green]" if in_container else "[yellow]No[/yellow]")
    table.add_row("Container Type", container_type)
    table.add_row("User", os.environ.get("USER", "unknown"))
    table.add_row("Home", str(Path.home()))

    claude_dir = get_container_claude_dir()
    table.add_row("Claude Dir", str(claude_dir))
    table.add_row("Claude Dir Exists", "[green]Yes[/green]" if claude_dir.exists() else "[red]No[/red]")

    host_sync = get_host_sync_dir()
    table.add_row("Host Sync Dir", str(host_sync) if host_sync else "[yellow]Not configured[/yellow]")

    console.print(table)

    # Show data summary
    if claude_dir.exists():
        console.print()

        data_table = Table(title="Container Data")
        data_table.add_column("Type", style="cyan")
        data_table.add_column("Count/Size", style="white")

        jsonl_files = get_jsonl_files(claude_dir)
        data_table.add_row("JSONL Files", str(len(jsonl_files)))

        projects = get_projects_data(claude_dir)
        data_table.add_row("Projects", str(len(projects)))

        # Check for database (try both names)
        usage_db = claude_dir / "usage" / "usage_history.db"
        if not usage_db.exists():
            usage_db = claude_dir / "usage" / "usage.db"

        if usage_db.exists():
            size_mb = usage_db.stat().st_size / (1024 * 1024)
            data_table.add_row("CCG Database", f"{size_mb:.2f} MB")
        else:
            data_table.add_row("CCG Database", "[dim]Not found[/dim]")

        console.print(data_table)

    # Show sync instructions if not configured
    if in_container and not host_sync:
        console.print()
        console.print(Panel(
            "[yellow]Host sync not configured.[/yellow]\n\n"
            "To enable sync, add this mount to your devcontainer.json:\n"
            '[cyan]"source=${localEnv:HOME}/.claude-sync,target=/home/dev/.claude-host-sync,type=bind"[/cyan]\n\n'
            "Or set CLAUDE_HOST_SYNC_DIR environment variable.",
            title="Setup Required",
            border_style="yellow",
        ))


def sync_command(
    direction: str = typer.Argument(
        "push",
        help="Sync direction: 'push' (container→host) or 'pull' (host→container)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run", "-n",
        help="Show what would be synced without making changes",
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Force sync even if not in container",
    ),
    target: str | None = typer.Option(
        None,
        "--target", "-t",
        help="Target directory for sync (overrides auto-detection)",
    ),
):
    """
    Sync Claude Code data between container and host.

    Examples:
        ccg container sync push              Push container data to host
        ccg container sync push --dry-run    Preview what would be synced
        ccg container sync pull              Pull host data to container
    """
    in_container = is_in_container()

    if not in_container and not force:
        console.print("[yellow]Warning:[/yellow] Not running in a container.")
        console.print("Use [cyan]--force[/cyan] to sync anyway.")
        raise typer.Exit(1)

    claude_dir = get_container_claude_dir()

    if target:
        host_dir = Path(target)
    else:
        host_dir = get_host_sync_dir()

    if not host_dir:
        console.print("[red]Error:[/red] No host sync directory configured.")
        console.print()
        console.print("Options:")
        console.print("  1. Mount a sync directory in your devcontainer.json")
        console.print("  2. Set CLAUDE_HOST_SYNC_DIR environment variable")
        console.print("  3. Use [cyan]--target /path/to/sync[/cyan] to specify manually")
        raise typer.Exit(1)

    if direction == "push":
        console.print("[cyan]Syncing:[/cyan] Container → Host")
        console.print(f"  From: {claude_dir}")
        console.print(f"  To:   {host_dir}")

        if dry_run:
            console.print("[yellow]  (dry run - no changes will be made)[/yellow]")

        console.print()

        # Sync JSONL files
        jsonl_stats = sync_jsonl_to_host(claude_dir, host_dir, dry_run)
        console.print(f"[green]JSONL:[/green] {jsonl_stats['files_synced']} files, {jsonl_stats['records_synced']} records")

        if jsonl_stats["errors"]:
            for err in jsonl_stats["errors"]:
                console.print(f"  [red]Error:[/red] {err}")

        # Sync CCG database
        db_stats = sync_ccg_database(claude_dir, host_dir, dry_run)
        if db_stats["synced"]:
            console.print("[green]CCG Database:[/green] Synced")
            if db_stats.get("warning"):
                console.print(f"  [yellow]Warning:[/yellow] {db_stats['warning']}")
            if db_stats.get("backup_path"):
                console.print(f"  [dim]Backup:[/dim] {db_stats['backup_path']}")
        elif db_stats["error"]:
            console.print(f"[red]CCG Database:[/red] {db_stats['error']}")
        else:
            console.print("[dim]CCG Database:[/dim] Not found")

        console.print()
        if dry_run:
            console.print("[yellow]Dry run complete. Use without --dry-run to apply changes.[/yellow]")
        else:
            console.print("[green]Sync complete![/green]")

    elif direction == "pull":
        console.print("[cyan]Syncing:[/cyan] Host → Container")
        console.print(f"  From: {host_dir}")
        console.print(f"  To:   {claude_dir}")
        console.print()
        console.print("[yellow]Pull sync not yet implemented.[/yellow]")
        console.print("For now, use bind mounts to share host config with container.")

    else:
        console.print(f"[red]Error:[/red] Unknown direction '{direction}'")
        console.print("Use 'push' or 'pull'")
        raise typer.Exit(1)

# endregion
