"""
Sync setup command for Claude Goblin.

Interactive wizard for configuring storage format and sync provider.
Supports non-interactive mode via CLI flags.
"""
#region Imports
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
    "quack": {
        "name": "Quack (DuckDB remote protocol)",
        "description": "Push to a remote DuckDB server via Quack over Tailscale/WireGuard",
        "details": [
            "Requires DuckDB v1.5.2+ with quack extension on both ends",
            "Server binds to Tailscale IP only (not public)",
            "Token auth stored in macOS Keychain or env var",
        ],
        "requires": "DuckDB quack extension + Tailscale",
        "license": "Free",
        "recommended": True,
        "storage_formats": ["duckdb"],
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

DOCS_LINKS = {
    "sqlite": "https://sqlite.org/docs.html",
    "duckdb": "https://duckdb.org/docs/",
    "quack": "https://duckdb.org/2026/05/12/quack-remote-protocol",
    "onedrive": "https://onedrive.com/",
    "onelake": "https://learn.microsoft.com/fabric",
    "motherduck": "https://motherduck.com/docs/",
}
#endregion


#region Helper Functions


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
    table.add_row("  Quack", DOCS_LINKS["quack"], "Free, DuckDB remote protocol")
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

    elif selected_provider == "quack":
        # Quack-specific configuration
        if not yes:
            from rich.prompt import Prompt, Confirm
            host = Prompt.ask("Remote host (Tailscale FQDN or IP)", default="your-quack-host.example.com")
            port_str = Prompt.ask("Port", default="9494")
            disable_ssl = Confirm.ask("Disable SSL? (yes if using Tailscale WireGuard)", default=True)
            token_source = Prompt.ask("Token source", choices=["keychain", "env", "file"], default="keychain")
        else:
            host = workspace or ""  # reuse --workspace flag for host in non-interactive
            port_str = "9494"
            disable_ssl = True
            token_source = "keychain"

        sync_config = {
            "host": host,
            "port": int(port_str),
            "disable_ssl": disable_ssl,
            "token_source": token_source,
        }

        if token_source == "keychain":
            sync_config["keychain_service"] = "DuckDB Quack Token"
            sync_config["keychain_account"] = "duckdb-quack"
        elif token_source == "file":
            if not yes:
                token_file = Prompt.ask("Token file path", default="~/.config/duckdb/quack.env")
            else:
                token_file = "~/.config/duckdb/quack.env"
            sync_config["token_file"] = token_file

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
    user_config.set_sync_config(selected_provider, sync_config)

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
