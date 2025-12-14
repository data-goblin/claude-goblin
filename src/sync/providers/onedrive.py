"""
OneDrive sync provider for Claude Goblin.

Uses local OneDrive folder for synchronization.
OneDrive app handles the actual sync - this provider manages file placement.
"""
#region Imports
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from src.sync.providers.base import SyncProvider
#endregion


#region Provider


class OneDriveProvider(SyncProvider):
    """
    OneDrive provider using local folder sync.

    This provider places database files in the user's local OneDrive folder.
    The OneDrive desktop app handles actual sync to cloud.

    Benefits:
    - No additional setup required if OneDrive is already installed
    - Works across Windows, macOS, and Linux (via rclone or similar)

    Requirements:
    - OneDrive desktop app installed and signed in
    - Local OneDrive folder path
    """

    def __init__(self, path: Optional[str] = None, device_id: Optional[str] = None, **kwargs):
        """
        Initialize OneDrive provider.

        Args:
            path: Path to local OneDrive folder
            device_id: Device identifier for per-device files
        """
        self.onedrive_path = Path(path) if path else self._detect_onedrive_path()
        self.device_id = device_id
        self.sync_subfolder = "Apps/ClaudeGoblin"

    def _detect_onedrive_path(self) -> Optional[Path]:
        """
        Attempt to detect the OneDrive folder path.

        Returns:
            Path to OneDrive folder or None if not found
        """
        home = Path.home()

        # Common OneDrive paths by platform
        possible_paths = [
            # Windows
            home / "OneDrive",
            home / "OneDrive - Personal",
            # macOS
            home / "Library" / "CloudStorage" / "OneDrive-Personal",
            # Linux (via rclone mount)
            home / "OneDrive",
        ]

        for p in possible_paths:
            if p.exists():
                return p

        return None

    @property
    def name(self) -> str:
        return "OneDrive"

    @property
    def requires_account(self) -> bool:
        return True  # Microsoft account required

    @property
    def sync_dir(self) -> Optional[Path]:
        """Get the sync directory path."""
        if not self.onedrive_path:
            return None
        return self.onedrive_path / self.sync_subfolder

    def is_available(self) -> bool:
        """Check if OneDrive folder exists."""
        return self.onedrive_path is not None and self.onedrive_path.exists()

    def is_authenticated(self) -> bool:
        """
        Check if OneDrive is configured and accessible.

        For local folder sync, "authenticated" means the folder exists
        and appears to be syncing (has .odopen or similar marker).
        """
        if not self.is_available():
            return False

        # OneDrive folder exists - assume it's syncing
        # Could add more sophisticated checks for sync status
        return True

    def get_status(self) -> dict:
        """Get OneDrive status information."""
        status = {
            "available": self.is_available(),
            "path": str(self.onedrive_path) if self.onedrive_path else None,
            "sync_dir": str(self.sync_dir) if self.sync_dir else None,
            "sync_dir_exists": self.sync_dir.exists() if self.sync_dir else False,
        }

        if self.sync_dir and self.sync_dir.exists():
            # List device files
            db_files = list(self.sync_dir.glob("*.db")) + list(self.sync_dir.glob("*.duckdb"))
            status["device_files"] = [f.name for f in db_files]
            status["device_count"] = len(db_files)

        return status

    def push(self, local_path: Path) -> tuple[bool, str]:
        """
        Copy local database to OneDrive folder.

        Args:
            local_path: Path to local database file

        Returns:
            Tuple of (success, message)
        """
        if not self.is_available():
            return False, "OneDrive folder not found"

        if not local_path.exists():
            return False, f"Local file not found: {local_path}"

        # Ensure sync directory exists
        sync_dir = self.sync_dir
        if not sync_dir:
            return False, "OneDrive path not configured"

        sync_dir.mkdir(parents=True, exist_ok=True)

        # Determine target filename
        if self.device_id:
            target_name = f"{self.device_id}{local_path.suffix}"
        else:
            target_name = local_path.name

        target_path = sync_dir / target_name

        try:
            # Use atomic write pattern: copy to temp file, then rename
            # This prevents partial file states if sync triggers mid-write
            fd, temp_path_str = tempfile.mkstemp(
                suffix=local_path.suffix,
                prefix='.tmp_',
                dir=sync_dir
            )
            temp_path = Path(temp_path_str)
            try:
                os.close(fd)  # Close file descriptor, we'll use shutil
                shutil.copy2(local_path, temp_path)
                # Atomic rename (on POSIX; best-effort on Windows)
                temp_path.replace(target_path)
                return True, f"Copied to {target_path}"
            except Exception:
                # Clean up temp file on failure
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise
        except IOError as e:
            return False, f"Failed to copy: {e}"

    def pull(self, local_dir: Path) -> tuple[bool, str]:
        """
        List available device files in OneDrive folder.

        Args:
            local_dir: Local directory (not used for listing)

        Returns:
            Tuple of (success, message with file list)
        """
        if not self.is_available():
            return False, "OneDrive folder not found"

        sync_dir = self.sync_dir
        if not sync_dir or not sync_dir.exists():
            return False, "Sync folder not found"

        # List device files
        db_files = list(sync_dir.glob("*.db")) + list(sync_dir.glob("*.duckdb"))

        if not db_files:
            return True, "No device files found"

        file_list = ", ".join(f.name for f in db_files)
        return True, f"Found {len(db_files)} device file(s): {file_list}"

    def get_remote_devices(self) -> list[dict]:
        """Get list of device files in OneDrive folder."""
        devices = []

        if not self.sync_dir or not self.sync_dir.exists():
            return devices

        db_files = list(self.sync_dir.glob("*.db")) + list(self.sync_dir.glob("*.duckdb"))

        for f in db_files:
            device_id = f.stem
            devices.append({
                "id": device_id,
                "name": device_id,  # Could parse from metadata
                "last_sync": f.stat().st_mtime,
            })

        return devices


#endregion
