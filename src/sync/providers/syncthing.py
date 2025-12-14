"""
Syncthing sync provider for Claude Goblin.

Uses Syncthing CLI for P2P folder synchronization.
Syncthing handles the actual sync - this provider manages configuration.
"""
#region Imports
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from src.sync.providers.base import SyncProvider
#endregion


#region Provider


class SyncthingProvider(SyncProvider):
    """
    Syncthing provider for peer-to-peer folder sync.

    Syncthing manages its own sync process. This provider:
    - Detects Syncthing installation
    - Configures sync folders
    - Manages device connections
    - Reports sync status

    The actual data sync happens automatically when Syncthing daemon runs.
    """

    FOLDER_ID = "claude-usage"

    def __init__(self, sync_path: Optional[Path] = None, **kwargs):
        """
        Initialize Syncthing provider.

        Args:
            sync_path: Path to sync folder (default: ~/.claude/usage)
        """
        self.sync_path = sync_path or (Path.home() / ".claude" / "usage")

    @property
    def name(self) -> str:
        return "Syncthing"

    @property
    def requires_account(self) -> bool:
        return False

    def is_available(self) -> bool:
        """Check if Syncthing CLI is installed."""
        return shutil.which("syncthing") is not None

    def is_authenticated(self) -> bool:
        """
        Syncthing doesn't require authentication.
        Returns True if daemon can be reached.
        """
        if not self.is_available():
            return False

        try:
            result = subprocess.run(
                ["syncthing", "cli", "show", "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_status(self) -> dict:
        """Get Syncthing status information."""
        status = {
            "installed": self.is_available(),
            "daemon_running": False,
            "device_id": None,
            "folder_configured": False,
            "connected_devices": 0,
        }

        if not status["installed"]:
            return status

        # Check if daemon is running (platform-independent)
        try:
            if platform.system() == "Windows":
                # Windows: use tasklist
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq syncthing.exe", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                status["daemon_running"] = "syncthing.exe" in result.stdout
            else:
                # Unix-like: use pgrep
                result = subprocess.run(
                    ["pgrep", "-x", "syncthing"],
                    capture_output=True,
                    timeout=5,
                )
                status["daemon_running"] = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Get device ID
        try:
            result = subprocess.run(
                ["syncthing", "--device-id"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                status["device_id"] = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Check if folder is configured
        try:
            result = subprocess.run(
                ["syncthing", "cli", "config", "folders", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                status["folder_configured"] = self.FOLDER_ID in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return status

    def push(self, local_path: Path) -> tuple[bool, str]:
        """
        Syncthing sync is automatic - this ensures folder is configured.

        Args:
            local_path: Path to database file (should be in sync folder)

        Returns:
            Tuple of (success, message)
        """
        if not self.is_available():
            return False, "Syncthing is not installed"

        # Ensure sync folder exists
        self.sync_path.mkdir(parents=True, exist_ok=True)

        # Check if folder is already configured
        status = self.get_status()
        if status["folder_configured"]:
            return True, "Sync folder already configured - sync happens automatically"

        # Configure the folder
        try:
            result = subprocess.run(
                [
                    "syncthing", "cli", "config", "folders", "add",
                    "--id", self.FOLDER_ID,
                    "--path", str(self.sync_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return True, f"Sync folder configured at {self.sync_path}"
            else:
                if "already exists" in result.stderr.lower():
                    return True, "Sync folder already configured"
                return False, result.stderr.strip() or "Failed to configure folder"

        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except FileNotFoundError:
            return False, "Syncthing CLI not found"

    def pull(self, local_dir: Path) -> tuple[bool, str]:
        """
        Syncthing sync is automatic - this just checks status.

        Args:
            local_dir: Local directory (should be sync folder)

        Returns:
            Tuple of (success, message)
        """
        if not self.is_available():
            return False, "Syncthing is not installed"

        status = self.get_status()
        if not status["daemon_running"]:
            return False, "Syncthing daemon is not running"

        if not status["folder_configured"]:
            return False, "Sync folder not configured - run push first"

        return True, "Sync happens automatically when daemon is running"

    def get_remote_devices(self) -> list[dict]:
        """Get list of configured remote devices."""
        devices = []

        if not self.is_available():
            return devices

        try:
            result = subprocess.run(
                ["syncthing", "cli", "config", "devices", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Parse device list (format varies by syncthing version)
                for line in result.stdout.strip().split("\n"):
                    if line and not line.startswith("Device"):
                        parts = line.split()
                        if parts:
                            devices.append({
                                "id": parts[0],
                                "name": parts[1] if len(parts) > 1 else None,
                                "last_sync": None,  # Would need API to get this
                            })

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return devices

    def add_device(self, device_id: str, name: Optional[str] = None) -> tuple[bool, str]:
        """
        Add a remote device.

        Args:
            device_id: Syncthing device ID
            name: Optional human-readable name

        Returns:
            Tuple of (success, message)
        """
        if not self.is_available():
            return False, "Syncthing is not installed"

        try:
            cmd = [
                "syncthing", "cli", "config", "devices", "add",
                "--device-id", device_id,
            ]
            if name:
                cmd.extend(["--name", name])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return True, "Device added"
            else:
                if "already exists" in result.stderr.lower():
                    return True, "Device already configured"
                return False, result.stderr.strip() or "Failed to add device"

        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except FileNotFoundError:
            return False, "Syncthing CLI not found"

    def share_folder(self, device_id: str) -> tuple[bool, str]:
        """
        Share the claude-usage folder with a device.

        Args:
            device_id: Syncthing device ID

        Returns:
            Tuple of (success, message)
        """
        if not self.is_available():
            return False, "Syncthing is not installed"

        try:
            result = subprocess.run(
                [
                    "syncthing", "cli", "config", "folders", self.FOLDER_ID,
                    "devices", "add", "--device-id", device_id,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return True, "Folder shared with device"
            else:
                if "already" in result.stderr.lower():
                    return True, "Folder already shared"
                return False, result.stderr.strip() or "Failed to share folder"

        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except FileNotFoundError:
            return False, "Syncthing CLI not found"


#endregion
