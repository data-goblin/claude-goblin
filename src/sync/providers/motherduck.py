"""
MotherDuck sync provider for Claude Goblin.

Uses MotherDuck's DuckDB cloud service for synchronization.
Requires DuckDB storage format and MotherDuck account.
"""
#region Imports
import re
from pathlib import Path
from typing import Optional

from src.sync.providers.base import SyncProvider
#endregion


#region Constants
# Valid SQL identifier pattern (alphanumeric and underscore, not starting with digit)
VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

# Allowed table names for sync operations
ALLOWED_TABLES = frozenset([
    "daily_snapshots",
    "usage_records",
    "limits_snapshots",
    "file_metadata",
    "model_pricing",
])
#endregion


#region Helper Functions


def _is_valid_identifier(name: str) -> bool:
    """
    Check if a string is a valid SQL identifier.

    Args:
        name: String to validate

    Returns:
        True if valid identifier, False otherwise
    """
    if not name:
        return False
    return bool(VALID_IDENTIFIER_PATTERN.match(name))


def _validate_table_name(table: str) -> bool:
    """
    Validate that a table name is allowed for sync operations.

    Args:
        table: Table name to validate

    Returns:
        True if table is in allowed list

    Raises:
        ValueError: If table name is not allowed
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Table '{table}' is not allowed for sync. Allowed: {ALLOWED_TABLES}")
    return True


def _quote_identifier(name: str) -> str:
    """
    Quote a SQL identifier to prevent injection.

    Args:
        name: Identifier to quote

    Returns:
        Quoted identifier

    Raises:
        ValueError: If name is not a valid identifier
    """
    if not _is_valid_identifier(name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    # Double-quote the identifier for DuckDB
    return f'"{name}"'


#endregion


#region Provider


class MotherDuckProvider(SyncProvider):
    """
    MotherDuck provider for DuckDB cloud sync.

    MotherDuck provides cloud-hosted DuckDB databases that sync automatically.
    This is the only provider that requires DuckDB storage format.

    Benefits:
    - Native DuckDB integration
    - No file sync needed - direct database connection
    - 10GB free tier

    Requirements:
    - DuckDB storage format (not compatible with SQLite)
    - MotherDuck account and token
    - duckdb Python package
    """

    def __init__(
        self,
        token: Optional[str] = None,
        database: str = "claude_goblin_usage",
        device_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize MotherDuck provider.

        Args:
            token: MotherDuck authentication token
            database: MotherDuck database name
            device_id: Device identifier for multi-device support
        """
        self.token = token
        self.database = database
        self.device_id = device_id

    @property
    def name(self) -> str:
        return "MotherDuck"

    @property
    def requires_account(self) -> bool:
        return True  # MotherDuck account required

    @property
    def connection_string(self) -> Optional[str]:
        """
        Get MotherDuck connection string.

        Returns:
            Connection string like "md:claude_goblin_usage?motherduck_token=xxx"

        Note:
            This contains the actual token. Use redacted_connection_string for logging.
        """
        if not self.token:
            return None

        return f"md:{self.database}?motherduck_token={self.token}"

    @property
    def redacted_connection_string(self) -> str:
        """
        Get connection string with token redacted for safe logging.

        Returns:
            Connection string with token replaced by [REDACTED]
        """
        return f"md:{self.database}?motherduck_token=[REDACTED]"

    def _has_duckdb(self) -> bool:
        """Check if DuckDB is installed."""
        try:
            import duckdb  # noqa: F401
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Check if MotherDuck access is available."""
        return self._has_duckdb()

    def is_authenticated(self) -> bool:
        """Check if authenticated to MotherDuck."""
        if not self.token:
            return False

        if not self._has_duckdb():
            return False

        conn = None
        try:
            import duckdb
            conn = duckdb.connect(self.connection_string)
            conn.execute("SELECT 1")
            return True
        except Exception:
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_status(self) -> dict:
        """Get MotherDuck status information."""
        status = {
            "duckdb_installed": self._has_duckdb(),
            "token_configured": bool(self.token),
            "database": self.database,
            "authenticated": False,
            "tables": [],
        }

        if self.is_authenticated():
            status["authenticated"] = True

            conn = None
            try:
                import duckdb
                conn = duckdb.connect(self.connection_string)
                result = conn.execute("SHOW TABLES").fetchall()
                status["tables"] = [row[0] for row in result]
            except Exception:
                pass
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        return status

    def push(self, local_path: Path) -> tuple[bool, str]:
        """
        Push local DuckDB data to MotherDuck.

        For MotherDuck, we attach the local database and merge tables
        to the cloud database. Uses INSERT OR IGNORE to prevent duplicates
        and preserve existing data from other devices.

        Args:
            local_path: Path to local DuckDB database

        Returns:
            Tuple of (success, message)
        """
        if not self._has_duckdb():
            return False, "DuckDB not installed. Run: uv pip install duckdb"

        if not self.token:
            return False, "MotherDuck token not configured"

        if not local_path.exists():
            return False, f"Local database not found: {local_path}"

        conn = None
        try:
            import duckdb

            # Connect to MotherDuck
            conn = duckdb.connect(self.connection_string)

            # Attach local database (path is safe - comes from Path object)
            conn.execute(f"ATTACH '{local_path}' AS local_db (READ_ONLY)")

            # Get tables from local database
            tables = conn.execute(
                "SELECT table_name FROM local_db.information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchall()

            if not tables:
                conn.execute("DETACH local_db")
                return False, "No tables found in local database"

            # Filter to only allowed tables and validate names
            table_names = []
            for t in tables:
                table_name = t[0]
                if table_name in ALLOWED_TABLES and _is_valid_identifier(table_name):
                    table_names.append(table_name)

            if not table_names:
                conn.execute("DETACH local_db")
                return False, "No valid tables found for sync"

            device_id = self.device_id or 'unknown'
            if not _is_valid_identifier(device_id.replace('-', '_')):
                # Sanitize device_id for SQL safety
                device_id = 'unknown'

            # Copy each table to MotherDuck using safe identifier quoting
            for table in table_names:
                quoted_table = _quote_identifier(table)

                # Check if table exists in MotherDuck
                existing = conn.execute(f"""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_name = '{table}'
                """).fetchone()[0]

                if existing == 0:
                    # Create new table with device column
                    conn.execute(f"""
                        CREATE TABLE {quoted_table} AS
                        SELECT
                            *,
                            ? AS sync_device_id
                        FROM local_db.{quoted_table}
                    """, [device_id])
                else:
                    # For existing tables, we need to be careful about merging
                    # First, delete existing records from this device, then insert new ones
                    # This ensures we don't lose data from other devices
                    conn.execute(f"""
                        DELETE FROM {quoted_table}
                        WHERE sync_device_id = ?
                    """, [device_id])

                    # Insert new records from this device
                    conn.execute(f"""
                        INSERT INTO {quoted_table}
                        SELECT
                            *,
                            ? AS sync_device_id
                        FROM local_db.{quoted_table}
                    """, [device_id])

            conn.execute("DETACH local_db")

            return True, f"Synced {len(table_names)} table(s) to MotherDuck: {', '.join(table_names)}"

        except Exception as e:
            return False, f"Sync failed: {e}"
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def pull(self, local_dir: Path) -> tuple[bool, str]:
        """
        Pull data from MotherDuck to local DuckDB.

        For aggregated views, pull combined data from all devices.

        Args:
            local_dir: Directory to store local database

        Returns:
            Tuple of (success, message)
        """
        if not self._has_duckdb():
            return False, "DuckDB not installed"

        if not self.token:
            return False, "MotherDuck token not configured"

        conn = None
        try:
            import duckdb

            # Connect to MotherDuck
            conn = duckdb.connect(self.connection_string)

            # Get table info
            result = conn.execute("SHOW TABLES").fetchall()
            tables = [row[0] for row in result]

            if not tables:
                return True, "No tables in MotherDuck database"

            # Get device count - only query allowed tables
            device_count = 0
            for table in tables:
                if table not in ALLOWED_TABLES or not _is_valid_identifier(table):
                    continue
                try:
                    quoted_table = _quote_identifier(table)
                    result = conn.execute(f"""
                        SELECT COUNT(DISTINCT sync_device_id) FROM {quoted_table}
                    """).fetchone()
                    if result:
                        device_count = max(device_count, result[0])
                except Exception:
                    pass

            return True, f"MotherDuck has {len(tables)} table(s) with data from {device_count} device(s)"

        except Exception as e:
            return False, f"Query failed: {e}"
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_remote_devices(self) -> list[dict]:
        """Get list of devices that have synced to MotherDuck."""
        devices = []

        if not self.is_authenticated():
            return devices

        conn = None
        try:
            import duckdb
            conn = duckdb.connect(self.connection_string)

            # Try to get unique device IDs from allowed tables with sync_device_id
            result = conn.execute("SHOW TABLES").fetchall()
            tables = [row[0] for row in result]

            seen_devices: set[str] = set()
            for table in tables:
                # Only query allowed tables with valid identifiers
                if table not in ALLOWED_TABLES or not _is_valid_identifier(table):
                    continue

                try:
                    quoted_table = _quote_identifier(table)
                    result = conn.execute(f"""
                        SELECT DISTINCT sync_device_id
                        FROM {quoted_table}
                        WHERE sync_device_id IS NOT NULL
                    """).fetchall()

                    for row in result:
                        device_id = row[0]
                        if device_id and device_id not in seen_devices:
                            seen_devices.add(device_id)
                            devices.append({
                                "id": device_id,
                                "name": device_id,
                                "last_sync": None,
                            })
                except Exception:
                    pass

        except Exception:
            pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        return devices


#endregion
