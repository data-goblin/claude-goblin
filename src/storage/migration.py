"""
Database migration utilities for Claude Goblin.

Handles:
- SQLite to DuckDB migration
- DuckDB to SQLite migration
- Adding device metadata columns to existing databases
"""
#region Imports
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
#endregion


#region Constants
DEVICE_COLUMNS = ["device_id", "device_name", "device_type"]

TABLES_WITH_DEVICE_COLUMNS = [
    "daily_snapshots",
    "usage_records",
    "limits_snapshots",
]

logger = logging.getLogger(__name__)
#endregion


#region Connection Context Managers


@contextmanager
def sqlite_connection(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for SQLite connections.

    Args:
        db_path: Path to the SQLite database file

    Yields:
        SQLite connection object
    """
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def duckdb_connection(db_path: Path) -> Generator:
    """
    Context manager for DuckDB connections.

    Args:
        db_path: Path to the DuckDB database file

    Yields:
        DuckDB connection object
    """
    if not DUCKDB_AVAILABLE:
        raise ImportError("DuckDB is not installed")
    conn = duckdb.connect(str(db_path))
    try:
        yield conn
    finally:
        conn.close()


#endregion


#region SQLite Device Column Migration


def migrate_sqlite_add_device_columns(
    db_path: Path,
    device_id: str,
    device_name: str,
    device_type: str,
) -> int:
    """
    Add device columns to existing SQLite database and backfill values.

    Args:
        db_path: Path to the SQLite database file
        device_id: Device identifier to backfill
        device_name: Device name to backfill
        device_type: Device type to backfill

    Returns:
        Number of records updated

    Raises:
        sqlite3.Error: If database operation fails
    """
    if not db_path.exists():
        return 0

    updated_count = 0

    with sqlite_connection(db_path) as conn:
        cursor = conn.cursor()

        for table in TABLES_WITH_DEVICE_COLUMNS:
            # Check if table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            """, (table,))

            if not cursor.fetchone():
                logger.debug(f"Table {table} does not exist, skipping")
                continue

            # Get existing columns
            cursor.execute(f"PRAGMA table_info({table})")
            existing_columns = [row[1] for row in cursor.fetchall()]

            # Add missing device columns
            for col in DEVICE_COLUMNS:
                if col not in existing_columns:
                    logger.info(f"Adding column {col} to table {table}")
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")

            # Backfill existing records that don't have device info
            cursor.execute(f"""
                UPDATE {table}
                SET device_id = ?, device_name = ?, device_type = ?
                WHERE device_id IS NULL
            """, (device_id, device_name, device_type))

            updated_count += cursor.rowcount

        conn.commit()

    return updated_count


def check_sqlite_has_device_columns(db_path: Path) -> bool:
    """
    Check if SQLite database has device metadata columns.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        True if all device columns exist in all tables
    """
    if not db_path.exists():
        return False

    with sqlite_connection(db_path) as conn:
        cursor = conn.cursor()

        for table in TABLES_WITH_DEVICE_COLUMNS:
            # Check if table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            """, (table,))

            if not cursor.fetchone():
                continue

            # Get existing columns
            cursor.execute(f"PRAGMA table_info({table})")
            existing_columns = {row[1] for row in cursor.fetchall()}

            # Check if all device columns exist
            for col in DEVICE_COLUMNS:
                if col not in existing_columns:
                    return False

        return True


#endregion


#region DuckDB Device Column Migration


def migrate_duckdb_add_device_columns(
    db_path: Path,
    device_id: str,
    device_name: str,
    device_type: str,
) -> int:
    """
    Add device columns to existing DuckDB database and backfill values.

    Args:
        db_path: Path to the DuckDB database file
        device_id: Device identifier to backfill
        device_name: Device name to backfill
        device_type: Device type to backfill

    Returns:
        Number of records updated

    Raises:
        ImportError: If DuckDB is not installed
    """
    if not DUCKDB_AVAILABLE:
        raise ImportError("DuckDB is not installed")

    if not db_path.exists():
        return 0

    updated_count = 0

    with duckdb_connection(db_path) as conn:
        for table in TABLES_WITH_DEVICE_COLUMNS:
            # Check if table exists
            result = conn.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_name = ?
            """, [table]).fetchone()

            if not result:
                logger.debug(f"Table {table} does not exist, skipping")
                continue

            # Get existing columns
            columns_result = conn.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = ?
            """, [table]).fetchall()
            existing_columns = {row[0] for row in columns_result}

            # Add missing device columns
            for col in DEVICE_COLUMNS:
                if col not in existing_columns:
                    logger.info(f"Adding column {col} to table {table}")
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} VARCHAR")

            # Backfill existing records
            conn.execute(f"""
                UPDATE {table}
                SET device_id = ?, device_name = ?, device_type = ?
                WHERE device_id IS NULL
            """, [device_id, device_name, device_type])

            # DuckDB doesn't have rowcount, count manually
            count = conn.execute(f"""
                SELECT COUNT(*) FROM {table}
                WHERE device_id = ?
            """, [device_id]).fetchone()[0]
            updated_count += count

    return updated_count


#endregion


#region SQLite to DuckDB Migration


class MigrationError(Exception):
    """Raised when a migration operation fails."""
    pass


def migrate_sqlite_to_duckdb(
    sqlite_path: Path,
    duckdb_path: Path,
    device_id: Optional[str] = None,
    device_name: Optional[str] = None,
    device_type: Optional[str] = None,
) -> dict:
    """
    Migrate data from SQLite to DuckDB.

    Args:
        sqlite_path: Path to source SQLite database
        duckdb_path: Path to destination DuckDB database
        device_id: Optional device identifier to add during migration
        device_name: Optional device name to add during migration
        device_type: Optional device type to add during migration

    Returns:
        Dictionary with migration statistics and any errors

    Raises:
        ImportError: If DuckDB is not installed
        FileNotFoundError: If SQLite database doesn't exist
        MigrationError: If critical migration failure occurs
    """
    if not DUCKDB_AVAILABLE:
        raise ImportError("DuckDB is not installed")

    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    # Initialize DuckDB
    from src.storage.duckdb_backend import init_database as init_duckdb
    init_duckdb(duckdb_path)

    stats = {
        "daily_snapshots": 0,
        "usage_records": 0,
        "limits_snapshots": 0,
        "file_metadata": 0,
        "model_pricing": 0,
        "errors": [],
    }

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    duckdb_conn = duckdb.connect(str(duckdb_path))

    try:
        sqlite_cursor = sqlite_conn.cursor()

        # Migrate daily_snapshots
        try:
            sqlite_cursor.execute("SELECT * FROM daily_snapshots")
            for row in sqlite_cursor.fetchall():
                row_dict = dict(row)
                duckdb_conn.execute("""
                    INSERT OR REPLACE INTO daily_snapshots (
                        date, total_prompts, total_responses, total_sessions,
                        total_tokens, input_tokens, output_tokens,
                        cache_creation_tokens, cache_read_tokens, snapshot_timestamp,
                        device_id, device_name, device_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    row_dict["date"],
                    row_dict["total_prompts"],
                    row_dict["total_responses"],
                    row_dict["total_sessions"],
                    row_dict["total_tokens"],
                    row_dict["input_tokens"],
                    row_dict["output_tokens"],
                    row_dict["cache_creation_tokens"],
                    row_dict["cache_read_tokens"],
                    row_dict["snapshot_timestamp"],
                    row_dict.get("device_id") or device_id,
                    row_dict.get("device_name") or device_name,
                    row_dict.get("device_type") or device_type,
                ])
                stats["daily_snapshots"] += 1
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e).lower():
                logger.warning(f"Error migrating daily_snapshots: {e}")
                stats["errors"].append(f"daily_snapshots: {e}")

        # Migrate usage_records
        try:
            sqlite_cursor.execute("SELECT * FROM usage_records")
            for row in sqlite_cursor.fetchall():
                row_dict = dict(row)

                # Check if record already exists
                existing = duckdb_conn.execute("""
                    SELECT 1 FROM usage_records
                    WHERE session_id = ? AND message_uuid = ?
                """, [row_dict["session_id"], row_dict["message_uuid"]]).fetchone()

                if not existing:
                    next_id = duckdb_conn.execute(
                        "SELECT nextval('usage_records_id_seq')"
                    ).fetchone()[0]

                    duckdb_conn.execute("""
                        INSERT INTO usage_records (
                            id, date, timestamp, session_id, message_uuid, message_type,
                            model, folder, git_branch, version,
                            input_tokens, output_tokens,
                            cache_creation_tokens, cache_read_tokens, total_tokens,
                            device_id, device_name, device_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        next_id,
                        row_dict["date"],
                        row_dict["timestamp"],
                        row_dict["session_id"],
                        row_dict["message_uuid"],
                        row_dict["message_type"],
                        row_dict["model"],
                        row_dict["folder"],
                        row_dict["git_branch"],
                        row_dict["version"],
                        row_dict["input_tokens"],
                        row_dict["output_tokens"],
                        row_dict["cache_creation_tokens"],
                        row_dict["cache_read_tokens"],
                        row_dict["total_tokens"],
                        row_dict.get("device_id") or device_id,
                        row_dict.get("device_name") or device_name,
                        row_dict.get("device_type") or device_type,
                    ])
                    stats["usage_records"] += 1
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e).lower():
                logger.warning(f"Error migrating usage_records: {e}")
                stats["errors"].append(f"usage_records: {e}")

        # Migrate limits_snapshots
        try:
            sqlite_cursor.execute("SELECT * FROM limits_snapshots")
            for row in sqlite_cursor.fetchall():
                row_dict = dict(row)
                duckdb_conn.execute("""
                    INSERT OR REPLACE INTO limits_snapshots (
                        timestamp, date, session_pct, week_pct, opus_pct,
                        session_reset, week_reset, opus_reset,
                        device_id, device_name, device_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    row_dict["timestamp"],
                    row_dict["date"],
                    row_dict["session_pct"],
                    row_dict["week_pct"],
                    row_dict["opus_pct"],
                    row_dict["session_reset"],
                    row_dict["week_reset"],
                    row_dict["opus_reset"],
                    row_dict.get("device_id") or device_id,
                    row_dict.get("device_name") or device_name,
                    row_dict.get("device_type") or device_type,
                ])
                stats["limits_snapshots"] += 1
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e).lower():
                logger.warning(f"Error migrating limits_snapshots: {e}")
                stats["errors"].append(f"limits_snapshots: {e}")

        # Migrate file_metadata
        try:
            sqlite_cursor.execute("SELECT * FROM file_metadata")
            for row in sqlite_cursor.fetchall():
                row_dict = dict(row)
                duckdb_conn.execute("""
                    INSERT OR REPLACE INTO file_metadata (
                        file_path, mtime_ns, size_bytes, record_count, last_parsed
                    ) VALUES (?, ?, ?, ?, ?)
                """, [
                    row_dict["file_path"],
                    row_dict["mtime_ns"],
                    row_dict["size_bytes"],
                    row_dict["record_count"],
                    row_dict["last_parsed"],
                ])
                stats["file_metadata"] += 1
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e).lower():
                logger.warning(f"Error migrating file_metadata: {e}")
                stats["errors"].append(f"file_metadata: {e}")

        logger.info(f"Migration complete: {stats}")

    finally:
        sqlite_conn.close()
        duckdb_conn.close()

    return stats


#endregion


#region DuckDB to SQLite Migration


def migrate_duckdb_to_sqlite(
    duckdb_path: Path,
    sqlite_path: Path,
    device_id: Optional[str] = None,
    device_name: Optional[str] = None,
    device_type: Optional[str] = None,
) -> dict:
    """
    Migrate data from DuckDB to SQLite.

    Args:
        duckdb_path: Path to source DuckDB database
        sqlite_path: Path to destination SQLite database
        device_id: Optional device identifier to add during migration
        device_name: Optional device name to add during migration
        device_type: Optional device type to add during migration

    Returns:
        Dictionary with migration statistics and any errors

    Raises:
        ImportError: If DuckDB is not installed
        FileNotFoundError: If DuckDB database doesn't exist
        MigrationError: If critical migration failure occurs
    """
    if not DUCKDB_AVAILABLE:
        raise ImportError("DuckDB is not installed")

    if not duckdb_path.exists():
        raise FileNotFoundError(f"DuckDB database not found: {duckdb_path}")

    # Initialize SQLite
    from src.storage.snapshot_db import init_database as init_sqlite
    init_sqlite(sqlite_path)

    # Add device columns to SQLite if needed
    migrate_sqlite_add_device_columns(
        sqlite_path,
        device_id or "unknown",
        device_name or "unknown",
        device_type or "unknown",
    )

    stats = {
        "daily_snapshots": 0,
        "usage_records": 0,
        "limits_snapshots": 0,
        "file_metadata": 0,
        "errors": [],
    }

    duckdb_conn = duckdb.connect(str(duckdb_path))
    sqlite_conn = sqlite3.connect(sqlite_path)

    try:
        sqlite_cursor = sqlite_conn.cursor()

        # Migrate daily_snapshots
        try:
            rows = duckdb_conn.execute("SELECT * FROM daily_snapshots").fetchall()
            columns = [desc[0] for desc in duckdb_conn.description]

            for row in rows:
                row_dict = dict(zip(columns, row))
                sqlite_cursor.execute("""
                    INSERT OR REPLACE INTO daily_snapshots (
                        date, total_prompts, total_responses, total_sessions,
                        total_tokens, input_tokens, output_tokens,
                        cache_creation_tokens, cache_read_tokens, snapshot_timestamp,
                        device_id, device_name, device_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_dict["date"],
                    row_dict["total_prompts"],
                    row_dict["total_responses"],
                    row_dict["total_sessions"],
                    row_dict["total_tokens"],
                    row_dict["input_tokens"],
                    row_dict["output_tokens"],
                    row_dict["cache_creation_tokens"],
                    row_dict["cache_read_tokens"],
                    row_dict["snapshot_timestamp"],
                    row_dict.get("device_id") or device_id,
                    row_dict.get("device_name") or device_name,
                    row_dict.get("device_type") or device_type,
                ))
                stats["daily_snapshots"] += 1
        except duckdb.CatalogException as e:
            if "not exist" not in str(e).lower():
                logger.warning(f"Error migrating daily_snapshots: {e}")
                stats["errors"].append(f"daily_snapshots: {e}")

        # Migrate usage_records
        try:
            rows = duckdb_conn.execute("SELECT * FROM usage_records").fetchall()
            columns = [desc[0] for desc in duckdb_conn.description]

            for row in rows:
                row_dict = dict(zip(columns, row))
                try:
                    sqlite_cursor.execute("""
                        INSERT INTO usage_records (
                            date, timestamp, session_id, message_uuid, message_type,
                            model, folder, git_branch, version,
                            input_tokens, output_tokens,
                            cache_creation_tokens, cache_read_tokens, total_tokens,
                            device_id, device_name, device_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row_dict["date"],
                        row_dict["timestamp"],
                        row_dict["session_id"],
                        row_dict["message_uuid"],
                        row_dict["message_type"],
                        row_dict["model"],
                        row_dict["folder"],
                        row_dict["git_branch"],
                        row_dict["version"],
                        row_dict["input_tokens"],
                        row_dict["output_tokens"],
                        row_dict["cache_creation_tokens"],
                        row_dict["cache_read_tokens"],
                        row_dict["total_tokens"],
                        row_dict.get("device_id") or device_id,
                        row_dict.get("device_name") or device_name,
                        row_dict.get("device_type") or device_type,
                    ))
                    stats["usage_records"] += 1
                except sqlite3.IntegrityError:
                    logger.debug("Skipping duplicate usage_record")
        except duckdb.CatalogException as e:
            if "not exist" not in str(e).lower():
                logger.warning(f"Error migrating usage_records: {e}")
                stats["errors"].append(f"usage_records: {e}")

        # Migrate limits_snapshots
        try:
            rows = duckdb_conn.execute("SELECT * FROM limits_snapshots").fetchall()
            columns = [desc[0] for desc in duckdb_conn.description]

            for row in rows:
                row_dict = dict(zip(columns, row))
                sqlite_cursor.execute("""
                    INSERT OR REPLACE INTO limits_snapshots (
                        timestamp, date, session_pct, week_pct, opus_pct,
                        session_reset, week_reset, opus_reset,
                        device_id, device_name, device_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_dict["timestamp"],
                    row_dict["date"],
                    row_dict["session_pct"],
                    row_dict["week_pct"],
                    row_dict["opus_pct"],
                    row_dict["session_reset"],
                    row_dict["week_reset"],
                    row_dict["opus_reset"],
                    row_dict.get("device_id") or device_id,
                    row_dict.get("device_name") or device_name,
                    row_dict.get("device_type") or device_type,
                ))
                stats["limits_snapshots"] += 1
        except duckdb.CatalogException as e:
            if "not exist" not in str(e).lower():
                logger.warning(f"Error migrating limits_snapshots: {e}")
                stats["errors"].append(f"limits_snapshots: {e}")

        # Migrate file_metadata
        try:
            rows = duckdb_conn.execute("SELECT * FROM file_metadata").fetchall()
            columns = [desc[0] for desc in duckdb_conn.description]

            for row in rows:
                row_dict = dict(zip(columns, row))
                sqlite_cursor.execute("""
                    INSERT OR REPLACE INTO file_metadata (
                        file_path, mtime_ns, size_bytes, record_count, last_parsed
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    row_dict["file_path"],
                    row_dict["mtime_ns"],
                    row_dict["size_bytes"],
                    row_dict["record_count"],
                    row_dict["last_parsed"],
                ))
                stats["file_metadata"] += 1
        except duckdb.CatalogException as e:
            if "not exist" not in str(e).lower():
                logger.warning(f"Error migrating file_metadata: {e}")
                stats["errors"].append(f"file_metadata: {e}")

        sqlite_conn.commit()
        logger.info(f"Migration complete: {stats}")

    finally:
        duckdb_conn.close()
        sqlite_conn.close()

    return stats


#endregion


#region Utility Functions


def get_migration_status(sqlite_path: Path, duckdb_path: Path) -> dict:
    """
    Get current migration status for both databases.

    Args:
        sqlite_path: Path to SQLite database
        duckdb_path: Path to DuckDB database

    Returns:
        Dictionary with status for each database
    """
    status = {
        "sqlite": {
            "exists": sqlite_path.exists(),
            "has_device_columns": False,
            "record_count": 0,
            "error": None,
        },
        "duckdb": {
            "exists": duckdb_path.exists(),
            "has_device_columns": False,
            "record_count": 0,
            "error": None,
        },
    }

    if sqlite_path.exists():
        status["sqlite"]["has_device_columns"] = check_sqlite_has_device_columns(sqlite_path)
        try:
            with sqlite_connection(sqlite_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM daily_snapshots")
                status["sqlite"]["record_count"] = cursor.fetchone()[0]
        except sqlite3.Error as e:
            status["sqlite"]["error"] = str(e)
            logger.warning(f"Error checking SQLite status: {e}")

    if DUCKDB_AVAILABLE and duckdb_path.exists():
        try:
            with duckdb_connection(duckdb_path) as conn:
                # Check for device columns
                columns = conn.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'daily_snapshots'
                """).fetchall()
                column_names = {row[0] for row in columns}
                status["duckdb"]["has_device_columns"] = all(
                    col in column_names for col in DEVICE_COLUMNS
                )

                # Get record count
                status["duckdb"]["record_count"] = conn.execute(
                    "SELECT COUNT(*) FROM daily_snapshots"
                ).fetchone()[0]
        except Exception as e:
            status["duckdb"]["error"] = str(e)
            logger.warning(f"Error checking DuckDB status: {e}")

    return status


#endregion
