"""
Sync setup command for Claude Goblin.

Interactive wizard for configuring storage format and sync provider.
Supports non-interactive mode via CLI flags.
"""
#region Imports
import shutil
import subprocess
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text

from src.config import user_config
#endregion


#region Constants
STORAGE_OPTIONS = {
    "sqlite": {
        "name": "SQLite",
        "description": "Lightweight, battle-tested, single-file database",
        "best_for": "Most users",
        "recommended": True,
    },
    "duckdb": {
        "name": "DuckDB",
        "description": "Analytical database, faster for complex queries",
        "best_for": "Power users, large datasets, MotherDuck cloud sync",
        "recommended": False,
    },
}

PROVIDER_OPTIONS = {
    "syncthing": {
        "name": "Syncthing",
        "description": "Peer-to-peer folder sync, encrypted, no cloud",
        "details": [
            "Free, no account required",
            "Data stays on your devices",
            "Devices must be online together to sync",
        ],
        "requires": None,
        "license": "Free",
        "recommended": True,
        "storage_formats": ["sqlite", "duckdb"],
    },
    "onedrive": {
        "name": "OneDrive (local folder)",
        "description": "Sync via your local OneDrive folder",
        "details": [
            "Requires OneDrive app installed and signed in",
            "Free tier: 5GB (personal) / 1TB (M365 license)",
            "Data stored in Microsoft cloud",
        ],
        "requires": "OneDrive app",
        "license": "Free 5GB / M365 1TB",
        "recommended": False,
        "storage_formats": ["sqlite", "duckdb"],
    },
    "onelake": {
        "name": "OneLake (Fabric lakehouse)",
        "description": "Sync to Microsoft Fabric lakehouse",
        "details": [
            "Requires Fabric capacity (F2+ or trial)",
            "Best for: Enterprise, Power BI integration",
        ],
        "requires": "Fabric license",
        "license": "Fabric capacity required",
        "recommended": False,
        "storage_formats": ["sqlite", "duckdb"],
    },
    "motherduck": {
        "name": "MotherDuck",
        "description": "DuckDB cloud service with managed sync",
        "details": [
            "Requires MotherDuck account",
            "Free tier: 10GB storage",
            "DuckDB-only (not compatible with SQLite)",
        ],
        "requires": "MotherDuck account",
        "license": "Free 10GB, account required",
        "recommended": False,
        "storage_formats": ["duckdb"],  # DuckDB only
    },
    "none": {
        "name": "None (local only)",
        "description": "No sync, data stays on this device",
        "details": [],
        "requires": None,
        "license": "N/A",
        "recommended": False,
        "storage_formats": ["sqlite", "duckdb"],
    },
}

PACKAGE_MANAGERS = {
    "brew": {"name": "Homebrew", "install_cmd": "brew install syncthing"},
    "apt": {"name": "apt", "install_cmd": "sudo apt install syncthing"},
    "dnf": {"name": "dnf", "install_cmd": "sudo dnf install syncthing"},
    "pacman": {"name": "pacman", "install_cmd": "sudo pacman -S syncthing"},
    "choco": {"name": "Chocolatey", "install_cmd": "choco install syncthing"},
    "winget": {"name": "winget", "install_cmd": "winget install Syncthing.Syncthing"},
}

DOCS_LINKS = {
    "sqlite": "https://sqlite.org/docs.html",
    "duckdb": "https://duckdb.org/docs/",
    "syncthing": "https://docs.syncthing.net/",
    "onedrive": "https://onedrive.com/",
    "onelake": "https://learn.microsoft.com/fabric",
    "motherduck": "https://motherduck.com/docs/",
}
#endregion


#region Helper Functions


def detect_package_managers() -> dict[str, str]:
    """
    Detect available package managers on the system.

    Returns:
        Dict mapping manager name to install command
    """
    managers = {}
    for pm, info in PACKAGE_MANAGERS.items():
        if shutil.which(pm):
            managers[pm] = info["install_cmd"]
    return managers


def check_syncthing_installed() -> bool:
    """Check if syncthing CLI is available."""
    return shutil.which("syncthing") is not None


def get_syncthing_device_id() -> Optional[str]:
    """
    Get the Syncthing device ID.

    Returns:
        Device ID string or None if not available
    """
    if not check_syncthing_installed():
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


def install_syncthing(console: Console, package_manager: str) -> bool:
    """
    Install Syncthing using the specified package manager.

    Args:
        console: Rich console for output
        package_manager: Package manager to use

    Returns:
        True if installation succeeded
    """
    if package_manager not in PACKAGE_MANAGERS:
        return False

    # Use pre-defined command lists to avoid command injection
    # Each command is defined as a list of arguments, not a string to split
    INSTALL_COMMANDS = {
        "brew": ["brew", "install", "syncthing"],
        "apt": ["sudo", "apt", "install", "-y", "syncthing"],
        "dnf": ["sudo", "dnf", "install", "-y", "syncthing"],
        "pacman": ["sudo", "pacman", "-S", "--noconfirm", "syncthing"],
        "choco": ["choco", "install", "-y", "syncthing"],
        "winget": ["winget", "install", "--accept-package-agreements", "Syncthing.Syncthing"],
    }

    if package_manager not in INSTALL_COMMANDS:
        return False

    cmd_list = INSTALL_COMMANDS[package_manager]
    display_cmd = PACKAGE_MANAGERS[package_manager]["install_cmd"]
    console.print(f"\n[dim]Running: {display_cmd}[/dim]\n")

    try:
        result = subprocess.run(
            cmd_list,
            capture_output=False,
            timeout=300,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def display_storage_options(console: Console) -> None:
    """Display storage format options."""
    console.print("\n[bold]STEP 1: STORAGE FORMAT[/bold]")
    console.print("-" * 22)
    console.print()

    for i, (key, opt) in enumerate(STORAGE_OPTIONS.items(), 1):
        rec = " [green](Recommended)[/green]" if opt["recommended"] else ""
        console.print(f"  [{i}] {opt['name']}{rec}")
        console.print(f"      [dim]{opt['description']}[/dim]")
        console.print(f"      [dim]Best for: {opt['best_for']}[/dim]")
        console.print()


def display_provider_options(console: Console, storage_format: str) -> list[str]:
    """
    Display sync provider options filtered by storage format.

    Returns:
        List of available provider keys in display order
    """
    console.print("\n[bold]STEP 2: SYNC PROVIDER[/bold]")
    console.print("-" * 21)
    console.print()

    available = []
    for key, opt in PROVIDER_OPTIONS.items():
        if storage_format in opt["storage_formats"]:
            available.append(key)

    for i, key in enumerate(available, 1):
        opt = PROVIDER_OPTIONS[key]
        rec = " [green](Recommended)[/green]" if opt["recommended"] else ""
        console.print(f"  [{i}] {opt['name']}{rec}")
        console.print(f"      [dim]{opt['description']}[/dim]")
        for detail in opt["details"]:
            console.print(f"      [dim]- {detail}[/dim]")
        console.print()

    return available


def display_epilog(console: Console) -> None:
    """Display documentation links epilog."""
    console.print()

    table = Table(title="Learn More", box=None, padding=(0, 2))
    table.add_column("Category", style="bold")
    table.add_column("Link")
    table.add_column("Notes", style="dim")

    table.add_row("Storage", "", "")
    table.add_row("  SQLite", DOCS_LINKS["sqlite"], "")
    table.add_row("  DuckDB", DOCS_LINKS["duckdb"], "")
    table.add_row("", "", "")
    table.add_row("Sync Providers", "", "")
    table.add_row("  Syncthing", DOCS_LINKS["syncthing"], "Free, no account")
    table.add_row("  OneDrive", DOCS_LINKS["onedrive"], "Free 5GB / M365 1TB")
    table.add_row("  OneLake", DOCS_LINKS["onelake"], "Fabric license req.")
    table.add_row("  MotherDuck", DOCS_LINKS["motherduck"], "Free 10GB, account req.")

    console.print(table)


#endregion


#region Command


def setup_sync_command(
    storage: Optional[str] = typer.Option(
        None, "--storage", "-s",
        help="Storage format: sqlite or duckdb"
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="Sync provider: syncthing, onedrive, onelake, motherduck, none"
    ),
    device_id: Optional[str] = typer.Option(
        None, "--device-id", "-d",
        help="Device identifier (auto-generated if not provided)"
    ),
    device_name: Optional[str] = typer.Option(
        None, "--device-name", "-n",
        help="Human-readable device name (hostname if not provided)"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Auto-confirm all prompts (for non-interactive use)"
    ),
    install: bool = typer.Option(
        False, "--install",
        help="Auto-install missing dependencies (requires --yes)"
    ),
    # OneLake-specific
    workspace: Optional[str] = typer.Option(
        None, "--workspace", "-w",
        help="OneLake workspace name (for OneLake provider)"
    ),
    lakehouse: Optional[str] = typer.Option(
        None, "--lakehouse", "-l",
        help="OneLake lakehouse name (for OneLake provider)"
    ),
    # MotherDuck-specific
    token: Optional[str] = typer.Option(
        None, "--token", "-t",
        help="MotherDuck token (for MotherDuck provider)"
    ),
    # OneDrive-specific
    onedrive_path: Optional[str] = typer.Option(
        None, "--onedrive-path",
        help="OneDrive folder path (for OneDrive provider)"
    ),
):
    """
    Configure cross-device sync for usage data.

    Interactive wizard that guides through:
    1. Storage format selection (SQLite or DuckDB)
    2. Sync provider selection (Syncthing, OneDrive, OneLake, MotherDuck, or None)

    Use --yes for non-interactive mode with all options specified via flags.
    """
    console = Console()

    console.print(Panel.fit(
        "[bold]Claude Goblin Sync Setup[/bold]\n"
        "[dim]Configure cross-device sync for your usage data[/dim]",
        border_style="blue",
    ))

    # Determine storage format
    if storage:
        if storage not in user_config.VALID_STORAGE_FORMATS:
            console.print(f"[red]Error: Invalid storage format '{storage}'[/red]")
            console.print(f"[yellow]Valid formats: {', '.join(user_config.VALID_STORAGE_FORMATS)}[/yellow]")
            raise typer.Exit(1)
        selected_storage = storage
    elif yes:
        console.print("[red]Error: --storage is required with --yes[/red]")
        raise typer.Exit(1)
    else:
        # Interactive storage selection
        display_storage_options(console)
        choice = Prompt.ask(
            "Select storage format",
            choices=["1", "2"],
            default="1",
        )
        selected_storage = "sqlite" if choice == "1" else "duckdb"

    console.print(f"\n[green]Selected storage:[/green] {STORAGE_OPTIONS[selected_storage]['name']}")

    # Determine sync provider
    if provider:
        if provider not in user_config.VALID_SYNC_PROVIDERS:
            console.print(f"[red]Error: Invalid sync provider '{provider}'[/red]")
            console.print(f"[yellow]Valid providers: {', '.join(user_config.VALID_SYNC_PROVIDERS)}[/yellow]")
            raise typer.Exit(1)

        # Check compatibility
        if selected_storage not in PROVIDER_OPTIONS[provider]["storage_formats"]:
            console.print(f"[red]Error: {provider} is not compatible with {selected_storage}[/red]")
            if provider == "motherduck":
                console.print("[yellow]MotherDuck requires DuckDB storage format[/yellow]")
            raise typer.Exit(1)

        selected_provider = provider
    elif yes:
        console.print("[red]Error: --provider is required with --yes[/red]")
        raise typer.Exit(1)
    else:
        # Interactive provider selection
        available_providers = display_provider_options(console, selected_storage)
        choices = [str(i) for i in range(1, len(available_providers) + 1)]
        choice = Prompt.ask(
            "Select sync provider",
            choices=choices,
            default="1",
        )
        selected_provider = available_providers[int(choice) - 1]

    console.print(f"[green]Selected provider:[/green] {PROVIDER_OPTIONS[selected_provider]['name']}")

    # Handle Syncthing installation
    if selected_provider == "syncthing":
        if not check_syncthing_installed():
            console.print("\n[yellow]Checking for Syncthing... not found[/yellow]")
            console.print("\nTo install Syncthing:")
            console.print("  [dim]macOS:   brew install syncthing[/dim]")
            console.print("  [dim]Linux:   apt install syncthing (or see https://syncthing.net/downloads)[/dim]")
            console.print("  [dim]Windows: choco install syncthing (or winget install Syncthing.Syncthing)[/dim]")

            managers = detect_package_managers()
            if managers:
                if yes and install:
                    # Auto-install with first available manager
                    pm = list(managers.keys())[0]
                    console.print(f"\n[dim]Auto-installing with {pm}...[/dim]")
                    if not install_syncthing(console, pm):
                        console.print("[red]Installation failed[/red]")
                        raise typer.Exit(1)
                elif not yes:
                    if Confirm.ask("\nInstall now?", default=True):
                        # Pick first available manager
                        pm = list(managers.keys())[0]
                        if not install_syncthing(console, pm):
                            console.print("[red]Installation failed[/red]")
                            raise typer.Exit(1)
                    else:
                        console.print("[yellow]Skipping installation. Please install Syncthing manually.[/yellow]")
                else:
                    console.print("[yellow]Use --install flag to auto-install dependencies[/yellow]")
                    raise typer.Exit(1)
            else:
                console.print("[red]No supported package manager found. Please install Syncthing manually.[/red]")
                if yes:
                    raise typer.Exit(1)
        else:
            console.print("\n[green]Syncthing found[/green]")

    # Initialize device info with validation
    if device_id:
        # Sanitize user-provided device_id
        sanitized_id = user_config.sanitize_device_id(device_id)
        if sanitized_id != device_id:
            console.print(f"[yellow]Device ID sanitized: '{device_id}' -> '{sanitized_id}'[/yellow]")
        try:
            user_config.set_device_id(sanitized_id)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    if device_name:
        try:
            user_config.set_device_name(device_name)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    final_device_id, final_device_name, final_device_type = user_config.initialize_device_info()

    # If using Syncthing and it's installed, try to get Syncthing device ID
    if selected_provider == "syncthing" and check_syncthing_installed():
        syncthing_id = get_syncthing_device_id()
        if syncthing_id:
            console.print(f"\n[dim]Syncthing Device ID: {syncthing_id[:20]}...[/dim]")

    # Build provider-specific config
    sync_config: dict = {}

    if selected_provider == "onelake":
        if not workspace:
            if yes:
                console.print("[red]Error: --workspace is required for OneLake provider[/red]")
                raise typer.Exit(1)
            workspace = Prompt.ask("OneLake workspace name")

        if not lakehouse:
            if yes:
                console.print("[red]Error: --lakehouse is required for OneLake provider[/red]")
                raise typer.Exit(1)
            lakehouse = Prompt.ask("OneLake lakehouse name")

        sync_config = {
            "workspace": workspace,
            "lakehouse": lakehouse,
        }

    elif selected_provider == "motherduck":
        if not token:
            if yes:
                console.print("[red]Error: --token is required for MotherDuck provider[/red]")
                raise typer.Exit(1)
            token = Prompt.ask("MotherDuck token", password=True)

        sync_config = {
            "token": token,
        }

    elif selected_provider == "onedrive":
        if not onedrive_path:
            if yes:
                console.print("[red]Error: --onedrive-path is required for OneDrive provider[/red]")
                raise typer.Exit(1)

            # Try to detect OneDrive path
            from pathlib import Path
            home = Path.home()
            possible_paths = [
                home / "OneDrive",
                home / "OneDrive - Personal",
                home / "Library" / "CloudStorage" / "OneDrive-Personal",
            ]
            detected = None
            for p in possible_paths:
                if p.exists():
                    detected = str(p)
                    break

            if detected:
                onedrive_path = Prompt.ask(
                    "OneDrive folder path",
                    default=detected,
                )
            else:
                onedrive_path = Prompt.ask("OneDrive folder path")

        sync_config = {
            "path": onedrive_path,
        }

    # Validate and save configuration
    if sync_config:
        is_valid, error_msg = user_config.validate_sync_config(sync_config, selected_provider)
        if not is_valid:
            console.print(f"[red]Error: {error_msg}[/red]")
            raise typer.Exit(1)

    user_config.set_storage_format(selected_storage)
    user_config.set_sync_provider(selected_provider)
    user_config.set_sync_config(sync_config)

    # Success message
    console.print()
    console.print(Panel.fit(
        f"[bold green]Setup complete![/bold green]\n\n"
        f"Storage:  {STORAGE_OPTIONS[selected_storage]['name']}\n"
        f"Provider: {PROVIDER_OPTIONS[selected_provider]['name']}\n"
        f"Device:   {final_device_name} ({final_device_id})\n"
        f"Type:     {final_device_type}",
        border_style="green",
    ))

    # Show epilog with documentation links
    display_epilog(console)


#endregion
