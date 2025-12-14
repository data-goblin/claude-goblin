"""
OneLake sync provider for Claude Goblin.

Uses Microsoft Fabric lakehouse for data synchronization.
Supports two modes:
1. Fabric CLI (fab) - simpler, recommended
2. Azure SDK - for programmatic access

Data flow:
1. Export local SQLite/DuckDB to Parquet
2. Upload to Files/claude-usage-raw/{device_id}.parquet
3. Optional: Fabric notebook converts raw Parquet to Delta table
"""
#region Imports
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from src.sync.providers.base import SyncProvider
#endregion


#region Provider


class OneLakeProvider(SyncProvider):
    """
    OneLake provider for Microsoft Fabric sync.

    Uploads usage data as Parquet files to a Fabric lakehouse.
    Each device writes its own Parquet file to avoid conflicts.

    The recommended approach:
    1. Raw Parquet files uploaded to Files/claude-usage-raw/
    2. A Fabric notebook merges these into a unified Delta table

    Requirements:
    - Microsoft Fabric capacity (F2+ or 60-day trial)
    - Authentication via fab CLI or Azure SDK
    """

    def __init__(
        self,
        workspace: Optional[str] = None,
        lakehouse: Optional[str] = None,
        device_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize OneLake provider.

        Args:
            workspace: Fabric workspace name
            lakehouse: Lakehouse name
            device_id: Device identifier for per-device files
        """
        self.workspace = workspace
        self.lakehouse = lakehouse
        self.device_id = device_id
        self.landing_zone = "claude-usage-raw"

    @property
    def name(self) -> str:
        return "OneLake"

    @property
    def requires_account(self) -> bool:
        return True  # Fabric license required

    @property
    def remote_path(self) -> Optional[str]:
        """
        Get the OneLake path for uploads.

        Returns:
            Path like "Workspace.Workspace/Lakehouse.Lakehouse/Files/claude-usage-raw/"
        """
        if not self.workspace or not self.lakehouse:
            return None

        return (
            f"{self.workspace}.Workspace/"
            f"{self.lakehouse}.Lakehouse/Files/{self.landing_zone}/"
        )

    def _has_fab_cli(self) -> bool:
        """Check if Fabric CLI is installed."""
        return shutil.which("fab") is not None

    def _check_fab_auth(self) -> bool:
        """Check if Fabric CLI is authenticated."""
        if not self._has_fab_cli():
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

    def is_available(self) -> bool:
        """Check if OneLake access is available."""
        # Check for fab CLI
        if self._has_fab_cli():
            return True

        # Check for Azure SDK
        try:
            from azure.storage.filedatalake import DataLakeServiceClient
            from azure.identity import DefaultAzureCredential
            return True
        except ImportError:
            pass

        return False

    def is_authenticated(self) -> bool:
        """Check if authenticated to OneLake."""
        if not self.workspace or not self.lakehouse:
            return False

        # Try fab CLI first
        if self._has_fab_cli():
            return self._check_fab_auth()

        # Try Azure SDK
        try:
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()
            # Just checking if we can get a credential
            return True
        except Exception:
            return False

    def get_status(self) -> dict:
        """Get OneLake status information."""
        status = {
            "workspace": self.workspace,
            "lakehouse": self.lakehouse,
            "fab_cli_installed": self._has_fab_cli(),
            "fab_cli_authenticated": self._check_fab_auth() if self._has_fab_cli() else False,
            "azure_sdk_available": False,
            "remote_path": self.remote_path,
        }

        # Check Azure SDK
        try:
            from azure.storage.filedatalake import DataLakeServiceClient
            status["azure_sdk_available"] = True
        except ImportError:
            pass

        return status

    def push(self, local_path: Path) -> tuple[bool, str]:
        """
        Upload local database as Parquet to OneLake.

        This method:
        1. Converts SQLite/DuckDB to Parquet (if needed)
        2. Uploads to Files/claude-usage-raw/{device_id}.parquet

        Args:
            local_path: Path to local database file

        Returns:
            Tuple of (success, message)
        """
        if not self.is_authenticated():
            return False, "Not authenticated to OneLake"

        if not self.remote_path:
            return False, "Workspace/Lakehouse not configured"

        if not local_path.exists():
            return False, f"Local file not found: {local_path}"

        # For now, we'll upload the raw database file
        # In a full implementation, we'd convert to Parquet first
        filename = f"{self.device_id}.db" if self.device_id else local_path.name
        remote_file = f"{self.remote_path}{filename}"

        # Try fab CLI
        if self._has_fab_cli() and self._check_fab_auth():
            return self._push_with_fab(local_path, remote_file)

        # Try Azure SDK
        return self._push_with_sdk(local_path, remote_file)

    def _push_with_fab(self, local_path: Path, remote_path: str) -> tuple[bool, str]:
        """Upload using Fabric CLI."""
        try:
            result = subprocess.run(
                ["fab", "cp", str(local_path), remote_path, "-f"],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                return True, f"Uploaded to {remote_path}"
            else:
                return False, result.stderr.strip() or "Upload failed"

        except subprocess.TimeoutExpired:
            return False, "Upload timed out"
        except FileNotFoundError:
            return False, "fab CLI not found"

    def _push_with_sdk(self, local_path: Path, remote_path: str) -> tuple[bool, str]:
        """Upload using Azure SDK."""
        try:
            from azure.storage.filedatalake import DataLakeServiceClient
            from azure.identity import DefaultAzureCredential

            account_url = "https://onelake.dfs.fabric.microsoft.com"
            credential = DefaultAzureCredential()
            service_client = DataLakeServiceClient(account_url, credential=credential)

            # Parse workspace from remote_path
            fs_client = service_client.get_file_system_client(self.workspace)

            # Get directory and filename from path
            dir_path = f"{self.lakehouse}.Lakehouse/Files/{self.landing_zone}"
            filename = local_path.name if not self.device_id else f"{self.device_id}{local_path.suffix}"

            dir_client = fs_client.get_directory_client(dir_path)
            file_client = dir_client.create_file(filename)

            with open(local_path, "rb") as f:
                data = f.read()
                file_client.upload_data(data, overwrite=True)

            return True, f"Uploaded to OneLake: {filename}"

        except ImportError:
            return False, "Azure SDK not installed. Run: uv pip install azure-storage-file-datalake azure-identity"
        except Exception as e:
            return False, f"Upload failed: {e}"

    def pull(self, local_dir: Path) -> tuple[bool, str]:
        """
        List available device files in OneLake.

        Args:
            local_dir: Local directory (not used for listing)

        Returns:
            Tuple of (success, message with file list)
        """
        if not self.is_authenticated():
            return False, "Not authenticated to OneLake"

        if not self.remote_path:
            return False, "Workspace/Lakehouse not configured"

        # Try fab CLI
        if self._has_fab_cli() and self._check_fab_auth():
            return self._list_with_fab()

        # Try Azure SDK
        return self._list_with_sdk()

    def _list_with_fab(self) -> tuple[bool, str]:
        """List files using Fabric CLI."""
        try:
            result = subprocess.run(
                ["fab", "ls", self.remote_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                files = [
                    line.strip() for line in result.stdout.splitlines()
                    if line.strip() and (line.endswith(".db") or line.endswith(".parquet"))
                ]
                if files:
                    return True, f"Found {len(files)} file(s): {', '.join(files)}"
                return True, "No device files found"
            else:
                return False, result.stderr.strip() or "Failed to list files"

        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except FileNotFoundError:
            return False, "fab CLI not found"

    def _list_with_sdk(self) -> tuple[bool, str]:
        """List files using Azure SDK."""
        try:
            from azure.storage.filedatalake import DataLakeServiceClient
            from azure.identity import DefaultAzureCredential

            account_url = "https://onelake.dfs.fabric.microsoft.com"
            credential = DefaultAzureCredential()
            service_client = DataLakeServiceClient(account_url, credential=credential)

            fs_client = service_client.get_file_system_client(self.workspace)
            dir_path = f"{self.lakehouse}.Lakehouse/Files/{self.landing_zone}"
            dir_client = fs_client.get_directory_client(dir_path)

            files = []
            for path in dir_client.get_paths():
                if path.name.endswith((".db", ".parquet", ".duckdb")):
                    files.append(Path(path.name).name)

            if files:
                return True, f"Found {len(files)} file(s): {', '.join(files)}"
            return True, "No device files found"

        except ImportError:
            return False, "Azure SDK not installed"
        except Exception as e:
            return False, f"Failed to list: {e}"

    def get_remote_devices(self) -> list[dict]:
        """Get list of device files in OneLake."""
        devices = []

        success, result = self.pull(Path("."))
        if not success:
            return devices

        # Parse file list from result message
        if "Found" in result:
            # Extract filenames from message like "Found 2 file(s): a.db, b.parquet"
            parts = result.split(": ", 1)
            if len(parts) == 2:
                filenames = [f.strip() for f in parts[1].split(",")]
                for f in filenames:
                    device_id = Path(f).stem
                    devices.append({
                        "id": device_id,
                        "name": device_id,
                        "last_sync": None,
                    })

        return devices


#endregion
