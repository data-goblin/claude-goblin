"""
Sync status command for Claude Goblin.

Displays current sync configuration and connection status.
"""
#region Imports
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
    sync_config = user_config.get_sync_config(sync_provider)

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
        "quack": "Quack (DuckDB remote)",
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
    if sync_provider == "onedrive":
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

    elif sync_provider == "quack":
        console.print()
        quack_table = Table(
            title="Quack Remote Status",
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        quack_table.add_column("Key", style="bold")
        quack_table.add_column("Value")

        host = sync_config.get("host", "Not set")
        port = sync_config.get("port", 9494)
        disable_ssl = sync_config.get("disable_ssl", True)
        token_source = sync_config.get("token_source", "keychain")

        quack_table.add_row("Host", f"{host}:{port}")
        quack_table.add_row("SSL", "[yellow]Disabled[/yellow] (WireGuard encrypts)" if disable_ssl else "[green]Enabled[/green]")
        quack_table.add_row("Token Source", token_source)

        # Test connectivity
        try:
            import subprocess as sp
            result = sp.run(
                ["ping", "-c", "1", "-t", "2", host.split(":")[0]],
                capture_output=True, timeout=3,
            )
            reachable = result.returncode == 0
            quack_table.add_row(
                "Reachable",
                "[green]Yes[/green]" if reachable else "[red]No[/red]"
            )
        except Exception:
            quack_table.add_row("Reachable", "[yellow]Unknown[/yellow]")

        console.print(quack_table)

    elif sync_provider == "none":
        console.print()
        console.print("[dim]No sync configured. Run 'ccg sync setup' to enable cross-device sync.[/dim]")


#endregion
