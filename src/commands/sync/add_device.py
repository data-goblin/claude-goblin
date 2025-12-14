"""
Add device command for Claude Goblin sync.

For Syncthing: adds a remote peer device by ID.
"""
#region Imports
import shutil
import subprocess

import typer
from rich.console import Console
from rich.panel import Panel

from src.config import user_config
#endregion


#region Helper Functions


def add_syncthing_device(device_id: str, name: str | None = None) -> tuple[bool, str]:
    """
    Add a remote device to Syncthing.

    Args:
        device_id: Syncthing device ID (XXXX-XXXX-... format)
        name: Optional human-readable name for the device

    Returns:
        Tuple of (success, message)
    """
    if not shutil.which("syncthing"):
        return False, "Syncthing is not installed"

    try:
        # Add the device
        cmd = ["syncthing", "cli", "config", "devices", "add", "--device-id", device_id]
        if name:
            cmd.extend(["--name", name])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True, f"Device {device_id[:12]}... added successfully"
        else:
            # Check if device already exists
            if "already exists" in result.stderr.lower():
                return True, "Device already configured"
            return False, result.stderr.strip() or "Unknown error"

    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, "Syncthing CLI not found"


def share_folder_with_device(device_id: str, folder_id: str = "claude-usage") -> tuple[bool, str]:
    """
    Share a Syncthing folder with a remote device.

    Args:
        device_id: Syncthing device ID
        folder_id: Folder ID to share (default: claude-usage)

    Returns:
        Tuple of (success, message)
    """
    try:
        cmd = [
            "syncthing", "cli", "config", "folders", folder_id,
            "devices", "add", "--device-id", device_id
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True, f"Folder shared with device"
        else:
            if "already" in result.stderr.lower():
                return True, "Folder already shared with device"
            return False, result.stderr.strip() or "Unknown error"

    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, "Syncthing CLI not found"


#endregion


#region Command


def add_device_command(
    device_id: str = typer.Argument(
        ...,
        help="Syncthing device ID (XXXX-XXXX-... format)"
    ),
    name: str | None = typer.Option(
        None, "--name", "-n",
        help="Human-readable name for the device"
    ),
    share: bool = typer.Option(
        True, "--share/--no-share",
        help="Share claude-usage folder with device (default: yes)"
    ),
):
    """
    Add a remote device for Syncthing sync.

    This command adds another device to your Syncthing configuration
    and optionally shares the claude-usage folder with it.

    Get the device ID from the remote machine by running:
      syncthing --device-id

    Example:
      ccg sync add-device MFZWI3D-BONSEZ4-... --name "Work Laptop"
    """
    console = Console()

    # Check that sync is configured with Syncthing
    sync_provider = user_config.get_sync_provider()
    if sync_provider != "syncthing":
        console.print(f"[red]Error: add-device is only for Syncthing sync[/red]")
        console.print(f"[dim]Current provider: {sync_provider}[/dim]")
        console.print("[yellow]Run 'ccg sync setup' and select Syncthing first[/yellow]")
        raise typer.Exit(1)

    # Check Syncthing is installed
    if not shutil.which("syncthing"):
        console.print("[red]Error: Syncthing is not installed[/red]")
        console.print("[yellow]Run 'ccg sync setup' to install Syncthing[/yellow]")
        raise typer.Exit(1)

    # Validate device ID format (basic check)
    if len(device_id) < 10 or "-" not in device_id:
        console.print("[red]Error: Invalid device ID format[/red]")
        console.print("[dim]Device IDs look like: MFZWI3D-BONSEZ4-YLTLTAZ-...[/dim]")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold]Adding Remote Device[/bold]\n"
        f"[dim]ID: {device_id[:20]}...[/dim]",
        border_style="blue",
    ))

    # Add the device
    success, message = add_syncthing_device(device_id, name)
    if success:
        console.print(f"[green]Device added:[/green] {message}")
    else:
        console.print(f"[red]Failed to add device:[/red] {message}")
        raise typer.Exit(1)

    # Share folder if requested
    if share:
        console.print()
        console.print("[dim]Sharing claude-usage folder...[/dim]")
        success, message = share_folder_with_device(device_id)
        if success:
            console.print(f"[green]Folder shared:[/green] {message}")
        else:
            console.print(f"[yellow]Warning: Could not share folder:[/yellow] {message}")
            console.print("[dim]You may need to share the folder manually via Syncthing UI[/dim]")

    console.print()
    console.print(Panel.fit(
        "[bold green]Device configured![/bold green]\n\n"
        "The remote device must also add your device ID:\n"
        f"  [dim]ccg sync add-device YOUR-DEVICE-ID[/dim]\n\n"
        "Once both devices are connected, usage data will sync\n"
        "when both devices are online.",
        border_style="green",
    ))


#endregion
