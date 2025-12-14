"""
Sync status command for Claude Goblin.

Displays current sync configuration and connection status.
"""
#region Imports
import platform
import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import user_config
#endregion


#region Helper Functions


def check_syncthing_running() -> bool:
    """Check if Syncthing daemon is running (cross-platform)."""
    try:
        if platform.system() == "Windows":
            # Use tasklist on Windows
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq syncthing.exe"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return "syncthing.exe" in result.stdout
        else:
            # Use pgrep on Unix-like systems
            result = subprocess.run(
                ["pgrep", "-x", "syncthing"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_syncthing_device_id() -> str | None:
    """Get the local Syncthing device ID."""
    if not shutil.which("syncthing"):
        return None

    try:
        result = subprocess.run(
            ["syncthing", "--device-id"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def check_onedrive_path(path: str) -> bool:
    """Check if OneDrive path exists."""
    return Path(path).exists()


def check_fab_auth() -> bool:
    """Check if Fabric CLI is authenticated."""
    if not shutil.which("fab"):
        return False

    try:
        result = subprocess.run(
            ["fab", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "Logged in" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


#endregion


#region Command


def sync_status_command():
    """
    Show current sync configuration and status.

    Displays:
    - Storage format and location
    - Sync provider and connection status
    - Device information
    """
    console = Console()

    # Get current configuration
    storage_format = user_config.get_storage_format()
    sync_provider = user_config.get_sync_provider()
    device_id = user_config.get_device_id()
    device_name = user_config.get_device_name()
    device_type = user_config.get_device_type_config()
    sync_config = user_config.get_sync_config()

    # Build status table
    table = Table(
        title="Sync Configuration",
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    table.add_column("Key", style="bold")
    table.add_column("Value")

    # Storage info
    storage_names = {"sqlite": "SQLite", "duckdb": "DuckDB"}
    table.add_row("Storage", storage_names.get(storage_format, storage_format))

    # Determine database path
    usage_dir = Path.home() / ".claude" / "usage"
    if device_id:
        db_ext = ".db" if storage_format == "sqlite" else ".duckdb"
        db_path = usage_dir / f"{device_id}{db_ext}"
    else:
        db_path = usage_dir / "usage_history.db"

    table.add_row("Path", str(db_path))
    table.add_row("", "")

    # Provider info
    provider_names = {
        "syncthing": "Syncthing (P2P)",
        "onedrive": "OneDrive (local folder)",
        "onelake": "OneLake (Fabric)",
        "motherduck": "MotherDuck (cloud)",
        "none": "None (local only)",
    }
    table.add_row("Provider", provider_names.get(sync_provider, sync_provider))

    # Device info
    if device_id:
        table.add_row("Device ID", device_id)
    if device_name:
        table.add_row("Device Name", device_name)
    if device_type:
        table.add_row("Device Type", device_type)

    console.print()
    console.print(table)

    # Provider-specific status
    if sync_provider == "syncthing":
        console.print()
        syncthing_table = Table(
            title="Syncthing Status",
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        syncthing_table.add_column("Key", style="bold")
        syncthing_table.add_column("Value")

        installed = shutil.which("syncthing") is not None
        syncthing_table.add_row(
            "Installed",
            "[green]Yes[/green]" if installed else "[red]No[/red]"
        )

        if installed:
            running = check_syncthing_running()
            syncthing_table.add_row(
                "Daemon",
                "[green]Running[/green]" if running else "[yellow]Stopped[/yellow]"
            )

            st_device_id = get_syncthing_device_id()
            if st_device_id:
                # Show truncated ID
                syncthing_table.add_row("Device ID", f"{st_device_id[:20]}...")

        console.print(syncthing_table)

        if not installed:
            console.print()
            console.print("[yellow]Run 'ccg sync setup' to install Syncthing[/yellow]")

    elif sync_provider == "onedrive":
        console.print()
        od_table = Table(
            title="OneDrive Status",
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        od_table.add_column("Key", style="bold")
        od_table.add_column("Value")

        od_path = sync_config.get("path", "")
        od_table.add_row("Folder", od_path)

        if od_path:
            exists = check_onedrive_path(od_path)
            od_table.add_row(
                "Status",
                "[green]Folder exists[/green]" if exists else "[red]Folder not found[/red]"
            )

        console.print(od_table)

    elif sync_provider == "onelake":
        console.print()
        ol_table = Table(
            title="OneLake Status",
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        ol_table.add_column("Key", style="bold")
        ol_table.add_column("Value")

        ol_table.add_row("Workspace", sync_config.get("workspace", "Not set"))
        ol_table.add_row("Lakehouse", sync_config.get("lakehouse", "Not set"))

        fab_installed = shutil.which("fab") is not None
        ol_table.add_row(
            "Fabric CLI",
            "[green]Installed[/green]" if fab_installed else "[yellow]Not found[/yellow]"
        )

        if fab_installed:
            authenticated = check_fab_auth()
            ol_table.add_row(
                "Authentication",
                "[green]Logged in[/green]" if authenticated else "[red]Not logged in[/red]"
            )

        console.print(ol_table)

    elif sync_provider == "motherduck":
        console.print()
        md_table = Table(
            title="MotherDuck Status",
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        md_table.add_column("Key", style="bold")
        md_table.add_column("Value")

        has_token = bool(sync_config.get("token"))
        md_table.add_row(
            "Token",
            "[green]Configured[/green]" if has_token else "[red]Not set[/red]"
        )

        console.print(md_table)

    elif sync_provider == "none":
        console.print()
        console.print("[dim]No sync configured. Run 'ccg sync setup' to enable cross-device sync.[/dim]")


#endregion
