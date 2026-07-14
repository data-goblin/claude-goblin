"""
Storage API dispatch layer.

Routes storage calls to the right backend (SQLite snapshot_db.py or
duckdb_backend.py) based on user config (storage_format), and resolves
the DB path via get_db_path() so per-device files are honored once
device_id is set.

Callers should import from this module instead of reaching directly
into snapshot_db or duckdb_backend, unless they need backend internals
(e.g. raw sqlite3 access for one-off scripts).
"""
#region Imports
from pathlib import Path

from src.config.user_config import (
    get_device_id as _cfg_device_id,
)
from src.config.user_config import (
    get_device_name as _cfg_device_name,
)
from src.config.user_config import (
    get_device_type_config as _cfg_device_type,
)
from src.models.usage_record import UsageRecord
from src.storage import get_backend_module, get_db_path

#endregion


#region Helpers


def _backend():
    return get_backend_module()


def current_db_path() -> Path:
    return get_db_path()


#endregion


#region Dispatch


def init_database(db: Path | None = None) -> None:
    _backend().init_database(db or get_db_path())


def save_snapshot(
    records: list[UsageRecord],
    storage_mode: str = "aggregate",
    device_id: str | None = None,
    device_name: str | None = None,
    device_type: str | None = None,
    db: Path | None = None,
) -> int:
    return _backend().save_snapshot(
        records,
        db_path=db or get_db_path(),
        storage_mode=storage_mode,
        device_id=device_id if device_id is not None else _cfg_device_id(),
        device_name=device_name if device_name is not None else _cfg_device_name(),
        device_type=device_type if device_type is not None else _cfg_device_type(),
    )


def save_file_aggregate(
    file_path: Path,
    records: list[UsageRecord],
    device_id: str | None = None,
    device_name: str | None = None,
    device_type: str | None = None,
    db: Path | None = None,
) -> int:
    return _backend().save_file_aggregate(
        file_path,
        records,
        db_path=db or get_db_path(),
        device_id=device_id if device_id is not None else _cfg_device_id(),
        device_name=device_name if device_name is not None else _cfg_device_name(),
        device_type=device_type if device_type is not None else _cfg_device_type(),
    )


def load_historical_records(
    start_date: str | None = None,
    end_date: str | None = None,
    db: Path | None = None,
) -> list[UsageRecord]:
    return _backend().load_historical_records(start_date, end_date, db_path=db or get_db_path())


def get_database_stats(db: Path | None = None) -> dict:
    return _backend().get_database_stats(db or get_db_path())


def get_stale_files(all_files: list[Path], db: Path | None = None):
    return _backend().get_stale_files(all_files, db_path=db or get_db_path())


def update_files_metadata(
    file_paths: list[Path],
    record_count: int = 0,
    db: Path | None = None,
    stats: dict[str, tuple[int, int]] | None = None,
) -> None:
    _backend().update_files_metadata(
        file_paths, record_count=record_count, db_path=db or get_db_path(), stats=stats
    )


def get_update_coverage(db: Path | None = None) -> dict:
    return _backend().get_update_coverage(db or get_db_path())


def remove_deleted_file_metadata(deleted_paths: list[str], db: Path | None = None) -> None:
    _backend().remove_deleted_file_metadata(deleted_paths, db_path=db or get_db_path())


def get_text_analysis_stats() -> dict:
    # Reads JSONL files directly; does not touch the configured DB, so
    # we always source from snapshot_db where the implementation lives.
    from src.storage.snapshot_db import get_text_analysis_stats as _impl
    return _impl()


def fill_empty_daily_snapshots(start_date: str, end_date: str, db: Path | None = None) -> int:
    return _backend().fill_empty_daily_snapshots(start_date, end_date, db_path=db or get_db_path())


#endregion
