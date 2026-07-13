"""
Sync status command for Claude Goblin.

Displays current sync configuration and connection status.
"""
#region Imports
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from src.config import user_config

#endregion


#region Helper Functions


def check_onedrive_path(path: str) -> bool:
    """Check if OneDrive path exists."""
    return Path(path).exists()


def check_fab_auth() -> bool:
    """Check if Fabric CLI is authenticated."""
    fab = shutil.which("fab")
    if not fab:
        return False

    try:
        result = subprocess.run(
            [fab, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "Logged in" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _panel_table(title: str) -> Table:
    table = Table(title=title, show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")
    return table


def _print_onedrive_panel(console: Console, sync_config: dict[str, Any]) -> None:
    table = _panel_table("OneDrive Status")
    od_path = sync_config.get("path", "")
    table.add_row("Folder", od_path)
    if od_path:
        exists = check_onedrive_path(od_path)
        table.add_row("Status", "[green]Folder exists[/green]" if exists else "[red]Folder not found[/red]")
    console.print()
    console.print(table)


def _print_onelake_panel(console: Console, sync_config: dict[str, Any], db_path: Path) -> None:
    table = _panel_table("OneLake Status")
    table.add_row("Workspace", sync_config.get("workspace", "Not set"))
    table.add_row("Lakehouse", sync_config.get("lakehouse", "Not set"))
    if sync_config.get("workspace_id"):
        table.add_row("Workspace ID", sync_config["workspace_id"])
    if sync_config.get("lakehouse_id"):
        table.add_row("Lakehouse ID", sync_config["lakehouse_id"])
    if sync_config.get("semantic_model_id"):
        table.add_row("Semantic Model", sync_config["semantic_model_id"])
    device_filter = sync_config.get("device_filter")
    if device_filter:
        table.add_row("Device Filter", ", ".join(device_filter))
    table.add_row("Push Interval", f"{sync_config.get('min_push_interval', 900)}s")

    if db_path.exists() and db_path.suffix == ".duckdb":
        try:
            from src.storage.duckdb_backend import get_sync_state
            from src.storage.onelake_remote import LAST_PUSH_KEY, WM_USAGE_KEY

            wm = get_sync_state(WM_USAGE_KEY, db_path=db_path)
            table.add_row("Usage Watermark", wm if wm is not None else "[dim]never pushed[/dim]")
            last_raw = get_sync_state(LAST_PUSH_KEY, db_path=db_path)
            if last_raw is not None:
                last = datetime.fromtimestamp(float(last_raw), tz=timezone.utc)
                table.add_row("Last Push", last.strftime("%Y-%m-%d %H:%M:%SZ"))
        except Exception:
            pass

    fab_installed = shutil.which("fab") is not None
    table.add_row("Fabric CLI", "[green]Installed[/green]" if fab_installed else "[yellow]Not found[/yellow]")
    if fab_installed:
        authenticated = check_fab_auth()
        table.add_row(
            "Authentication",
            "[green]Logged in[/green]" if authenticated else "[red]Not logged in[/red]",
        )
    console.print()
    console.print(table)


def _print_motherduck_panel(console: Console, sync_config: dict[str, Any]) -> None:
    table = _panel_table("MotherDuck Status")
    has_token = bool(sync_config.get("token"))
    table.add_row("Token", "[green]Configured[/green]" if has_token else "[red]Not set[/red]")
    console.print()
    console.print(table)


def _print_quack_panel(console: Console, sync_config: dict[str, Any]) -> None:
    table = _panel_table("Quack Remote Status")
    host = sync_config.get("host", "Not set")
    port = sync_config.get("port", 9494)
    disable_ssl = sync_config.get("disable_ssl", True)
    token_source = sync_config.get("token_source", "keychain")

    table.add_row("Host", f"{host}:{port}")
    table.add_row("SSL", "[yellow]Disabled[/yellow] (WireGuard encrypts)" if disable_ssl else "[green]Enabled[/green]")
    table.add_row("Token Source", token_source)

    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-t", "2", host.split(":")[0]],
            capture_output=True, timeout=3,
        )
        reachable = result.returncode == 0
        table.add_row("Reachable", "[green]Yes[/green]" if reachable else "[red]No[/red]")
    except Exception:
        table.add_row("Reachable", "[yellow]Unknown[/yellow]")

    console.print()
    console.print(table)


#endregion


#region Command


def sync_status_command() -> None:
    """
    Show current sync configuration and status.

    Displays:
    - Storage format and location
    - Every configured sync provider with its connection status
    - Device information
    """
    console = Console()

    # Get current configuration
    storage_format = user_config.get_storage_format()
    providers = user_config.get_sync_providers()
    device_id = user_config.get_device_id()
    device_name = user_config.get_device_name()
    device_type = user_config.get_device_type_config()

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
    }
    table.add_row(
        "Providers",
        ", ".join(provider_names.get(p, p) for p in providers) if providers else "None (local only)",
    )

    # Device info
    if device_id:
        table.add_row("Device ID", device_id)
    if device_name:
        table.add_row("Device Name", device_name)
    if device_type:
        table.add_row("Device Type", device_type)

    console.print()
    console.print(table)

    # One panel per configured provider so multi-sink setups show every sink
    for provider in providers:
        sync_config = user_config.get_sync_config(provider)
        if provider == "onedrive":
            _print_onedrive_panel(console, sync_config)
        elif provider == "onelake":
            _print_onelake_panel(console, sync_config, db_path)
        elif provider == "motherduck":
            _print_motherduck_panel(console, sync_config)
        elif provider == "quack":
            _print_quack_panel(console, sync_config)

    if not providers:
        console.print()
        console.print("[dim]No sync configured. Run 'ccg sync setup' to enable cross-device sync.[/dim]")


#endregion
