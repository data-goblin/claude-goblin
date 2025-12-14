"""
Storage layer for historical usage snapshots.

Provides database backends for SQLite and DuckDB, along with
migration utilities for switching between formats and adding
device metadata for cross-device sync.
"""
#region Imports
from pathlib import Path
from typing import Optional

from src.config.user_config import (
    get_storage_format,
    get_device_id,
    get_device_name,
    get_device_type_config,
    initialize_device_info,
)
#endregion


#region Constants
DEFAULT_USAGE_DIR = Path.home() / ".claude" / "usage"
#endregion


#region Database Path Functions


def get_db_path(
    device_id: Optional[str] = None,
    storage_format: Optional[str] = None,
) -> Path:
    """
    Get the database path based on storage format and device ID.

    When sync is configured, each device gets its own database file:
    - SQLite: ~/.claude/usage/{device_id}.db
    - DuckDB: ~/.claude/usage/{device_id}.duckdb

    When no sync is configured, uses the legacy path:
    - ~/.claude/usage/usage_history.db

    Args:
        device_id: Device identifier (uses config if not provided)
        storage_format: Storage format - "sqlite" or "duckdb" (uses config if not provided)

    Returns:
        Path to the database file
    """
    # Use provided values or fall back to config
    if storage_format is None:
        storage_format = get_storage_format()

    if device_id is None:
        device_id = get_device_id()

    # Determine file extension
    ext = ".duckdb" if storage_format == "duckdb" else ".db"

    # If device_id is set, use per-device file
    if device_id:
        return DEFAULT_USAGE_DIR / f"{device_id}{ext}"

    # Legacy path for non-sync mode
    return DEFAULT_USAGE_DIR / f"usage_history{ext}"


def get_legacy_db_path() -> Path:
    """
    Get the legacy database path (pre-sync).

    Returns:
        Path to ~/.claude/usage/usage_history.db
    """
    return DEFAULT_USAGE_DIR / "usage_history.db"


def ensure_device_initialized() -> tuple[str, str, str]:
    """
    Ensure device information is initialized.

    Calls initialize_device_info() if device_id is not set.

    Returns:
        Tuple of (device_id, device_name, device_type)
    """
    device_id = get_device_id()
    if not device_id:
        return initialize_device_info()

    device_name = get_device_name() or "unknown"
    device_type = get_device_type_config() or "unknown"
    return device_id, device_name, device_type


#endregion


#region Backend Selection


def get_backend_module():
    """
    Get the appropriate storage backend module based on config.

    Returns:
        The snapshot_db or duckdb_backend module
    """
    storage_format = get_storage_format()

    if storage_format == "duckdb":
        from src.storage import duckdb_backend
        return duckdb_backend
    else:
        from src.storage import snapshot_db
        return snapshot_db


def is_duckdb_mode() -> bool:
    """Check if currently configured for DuckDB storage."""
    return get_storage_format() == "duckdb"


#endregion


__all__ = [
    "get_db_path",
    "get_legacy_db_path",
    "ensure_device_initialized",
    "get_backend_module",
    "is_duckdb_mode",
    "DEFAULT_USAGE_DIR",
]
