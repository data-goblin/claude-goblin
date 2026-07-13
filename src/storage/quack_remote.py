"""
DuckDB Quack remote backend for Claude Goblin.

Handles push/pull of usage data to/from a remote DuckDB
instance via the Quack protocol over a Tailscale mesh network.
"""
#region Imports
import platform
import re
import subprocess
from datetime import datetime
from pathlib import Path

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

from src.config.user_config import get_sync_config
from src.models.usage_record import TokenUsage, UsageRecord

#endregion


#region Validation

SAFE_TOKEN_PATTERN = re.compile(r'^[A-Za-z0-9+/=_\-\.]{1,256}$')
SAFE_HOST_PATTERN = re.compile(r'^[A-Za-z0-9.\-:]+$')


def _validate_token(token: str) -> str:
    if not SAFE_TOKEN_PATTERN.match(token):
        raise ValueError("Token contains invalid characters")
    return token


def _validate_host(host: str) -> str:
    if not SAFE_HOST_PATTERN.match(host):
        raise ValueError(f"Host contains invalid characters: {host}")
    return host

#endregion


#region Token Retrieval


def get_token_from_keychain(service: str, account: str) -> str:
    result = subprocess.run(
        ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to read token from Keychain (service={service}, account={account})")
    return result.stdout.strip()


def get_quack_token() -> str:
    config = get_sync_config("quack")
    source = config.get("token_source", "keychain")

    if source == "keychain":
        if platform.system() != "Darwin":
            raise RuntimeError("Keychain token source only supported on macOS")
        return _validate_token(get_token_from_keychain(
            service=config.get("keychain_service", "DuckDB Quack Token"),
            account=config.get("keychain_account", "duckdb-quack"),
        ))
    elif source == "env":
        import os
        token = os.environ.get("QUACK_TOKEN")
        if not token:
            raise RuntimeError("QUACK_TOKEN environment variable not set")
        return _validate_token(token)
    elif source == "file":
        path = Path(config.get("token_file", "")).expanduser()
        if not path.exists():
            raise RuntimeError(f"Token file not found: {path}")
        return _validate_token(path.read_text().strip())

    raise RuntimeError(f"Unknown token source: {source}")


#endregion


#region Connection


def _require_duckdb():
    if not DUCKDB_AVAILABLE:
        raise ImportError(
            "DuckDB is not installed. Install with: uv pip install duckdb "
            "or: uv pip install claude-goblin[duckdb]"
        )


def _get_remote_params() -> tuple[str, int, bool]:
    config = get_sync_config("quack")
    host = config.get("host", "")
    if not host:
        raise RuntimeError("Quack remote host not configured. Run: ccg sync setup --provider quack")
    host = _validate_host(host)
    port = config.get("port", 9494)
    disable_ssl = config.get("disable_ssl", True)
    return host, port, disable_ssl


def connect_remote() -> "duckdb.DuckDBPyConnection":
    _require_duckdb()
    host, port, disable_ssl = _get_remote_params()
    token = get_quack_token()

    conn = duckdb.connect()
    conn.execute("LOAD quack")
    conn.execute(f"CREATE SECRET (TYPE quack, TOKEN '{token}')")

    addr = f"quack:{host}" if port == 9494 else f"quack:{host}:{port}"
    opts = " (DISABLE_SSL true)" if disable_ssl else ""
    conn.execute(f"ATTACH '{addr}' AS remote{opts}")
    return conn


#endregion


#region Schema


def init_remote_schema(conn: "duckdb.DuckDBPyConnection") -> None:
    # Quack does not currently implement CREATE SEQUENCE over the wire, so we
    # carry the local-source id through to the remote rather than autogenerating
    # one server-side. UNIQUE(session_id, message_uuid) is the real dedupe key;
    # the id column is just bookkeeping. Cross-device collisions on id are
    # theoretically possible but require many millions of rows per device — fine
    # for now.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS remote.usage_records (
            id BIGINT NOT NULL,
            date VARCHAR NOT NULL,
            timestamp VARCHAR NOT NULL,
            session_id VARCHAR NOT NULL,
            message_uuid VARCHAR NOT NULL,
            message_type VARCHAR NOT NULL,
            model VARCHAR,
            folder VARCHAR NOT NULL,
            git_branch VARCHAR,
            version VARCHAR NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cache_creation_tokens INTEGER NOT NULL,
            cache_read_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL,
            cache_creation_1h_tokens INTEGER DEFAULT 0,
            device_id VARCHAR,
            device_name VARCHAR,
            device_type VARCHAR,
            UNIQUE(session_id, message_uuid)
        )
    """)
    # Stays empty on remote: quack lacks DELETE/ON CONFLICT so daily rows
    # cannot be upserted; readers aggregate from remote.usage_records instead.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS remote.daily_snapshots (
            date VARCHAR PRIMARY KEY,
            total_prompts INTEGER NOT NULL,
            total_responses INTEGER NOT NULL,
            total_sessions INTEGER NOT NULL,
            total_tokens BIGINT NOT NULL,
            input_tokens BIGINT NOT NULL,
            output_tokens BIGINT NOT NULL,
            cache_creation_tokens BIGINT NOT NULL,
            cache_read_tokens BIGINT NOT NULL,
            snapshot_timestamp VARCHAR NOT NULL,
            device_id VARCHAR,
            device_name VARCHAR,
            device_type VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS remote.limits_snapshots (
            timestamp VARCHAR PRIMARY KEY,
            date VARCHAR NOT NULL,
            session_pct INTEGER,
            week_pct INTEGER,
            opus_pct INTEGER,
            session_reset VARCHAR,
            week_reset VARCHAR,
            opus_reset VARCHAR,
            device_id VARCHAR,
            device_name VARCHAR,
            device_type VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS remote.model_pricing (
            model_name VARCHAR PRIMARY KEY,
            input_price_per_mtok DOUBLE NOT NULL,
            output_price_per_mtok DOUBLE NOT NULL,
            cache_write_price_per_mtok DOUBLE NOT NULL,
            cache_read_price_per_mtok DOUBLE NOT NULL,
            last_updated VARCHAR NOT NULL,
            notes VARCHAR,
            cache_write_1h_price_per_mtok DOUBLE
        )
    """)
    # Best-effort migration for remotes created before the 1h cache-write
    # split; quack may not pass ALTER through, in which case a fresh remote
    # file (created with the schema above) is the migration path.
    for stmt in (
        "ALTER TABLE remote.usage_records ADD COLUMN IF NOT EXISTS cache_creation_1h_tokens INTEGER DEFAULT 0",
        "ALTER TABLE remote.model_pricing ADD COLUMN IF NOT EXISTS cache_write_1h_price_per_mtok DOUBLE",
    ):
        try:
            conn.execute(stmt)
        except duckdb.Error:
            pass


#endregion


#region Push

# sync_state keys on the local db tracking what has been pushed
WM_USAGE_KEY = "last_pushed_usage_id"
WM_LIMITS_KEY = "last_pushed_limits_ts"

# Set by `ccg update usage --rebuild`: the repair rewrites row identities, so
# pushing before the remote is purged would insert corrected rows alongside
# the old inflated ones (quack has no DELETE). Cleared by --quack-purged.
QUACK_PURGE_KEY = "quack_purge_required"

# Above this many candidate sessions the IN-list dedupe pull is no longer
# clearly cheaper than the full key pull, so fall back to the full path.
_MAX_INCREMENTAL_SESSIONS = 1000

_USAGE_COLS = (
    "id, date, timestamp, session_id, message_uuid, message_type, "
    "model, folder, git_branch, version, "
    "input_tokens, output_tokens, "
    "cache_creation_tokens, cache_read_tokens, total_tokens, "
    "cache_creation_1h_tokens, "
    "device_id, device_name, device_type"
)


def _read_local_push_state(local_db_path: Path) -> dict:
    """
    Read push watermarks and current local maxima from the local db.

    Returns:
        Dict with max_id, max_limits_ts, wm_id, wm_limits_ts
    """
    from src.storage.duckdb_backend import get_sync_state

    conn = duckdb.connect(str(local_db_path), read_only=True)
    try:
        try:
            max_id = conn.execute("SELECT MAX(id) FROM usage_records").fetchone()[0]
        except duckdb.Error:
            max_id = None
        try:
            max_limits_ts = conn.execute(
                "SELECT MAX(timestamp) FROM limits_snapshots"
            ).fetchone()[0]
        except duckdb.Error:
            max_limits_ts = None
    finally:
        conn.close()

    wm_raw = get_sync_state(WM_USAGE_KEY, db_path=local_db_path)
    return {
        "max_id": max_id,
        "max_limits_ts": max_limits_ts,
        "wm_id": int(wm_raw) if wm_raw is not None else None,
        "wm_limits_ts": get_sync_state(WM_LIMITS_KEY, db_path=local_db_path),
    }


def _push_usage_full(conn: "duckdb.DuckDBPyConnection") -> None:
    """
    Anti-join INSERT of all local usage_records missing from remote.

    Quack lacks ON CONFLICT and rejects mixing streaming scans + INSERTs in
    one query, so existing keys are materialized in a client temp table.
    """
    conn.execute("CREATE OR REPLACE TEMP TABLE existing_keys (session_id VARCHAR, message_uuid VARCHAR)")
    keys = conn.execute("SELECT session_id, message_uuid FROM remote.usage_records").fetchall()
    if keys:
        conn.executemany("INSERT INTO existing_keys VALUES (?, ?)", keys)
    conn.execute(f"""
        INSERT INTO remote.usage_records ({_USAGE_COLS})
        SELECT {_USAGE_COLS}
        FROM local_db.usage_records s
        WHERE NOT EXISTS (
            SELECT 1 FROM existing_keys k
            WHERE k.session_id = s.session_id AND k.message_uuid = s.message_uuid
        )
    """)
    conn.execute("DROP TABLE existing_keys")


def _push_usage_incremental(conn: "duckdb.DuckDBPyConnection", wm_id: int) -> int:
    """
    Push only local usage_records with id above the watermark.

    Dedupes against remote keys for the candidate sessions only, instead of
    pulling every remote key (the dominant cost of the full push).

    Returns:
        Number of records inserted, counted client-side before the INSERT

    Raises:
        RuntimeError: If the candidate session list is too large
        duckdb.Error: On any remote failure
    """
    sessions = [r[0] for r in conn.execute(
        "SELECT DISTINCT session_id FROM local_db.usage_records WHERE id > ?", [wm_id]
    ).fetchall()]
    if len(sessions) > _MAX_INCREMENTAL_SESSIONS:
        raise RuntimeError(f"{len(sessions)} candidate sessions; full push is cheaper")

    conn.execute("CREATE OR REPLACE TEMP TABLE existing_keys (session_id VARCHAR, message_uuid VARCHAR)")
    if sessions:
        placeholders = ", ".join("?" for _ in sessions)
        keys = conn.execute(
            f"SELECT session_id, message_uuid FROM remote.usage_records WHERE session_id IN ({placeholders})",
            sessions,
        ).fetchall()
        if keys:
            conn.executemany("INSERT INTO existing_keys VALUES (?, ?)", keys)

    anti_join = """
        FROM local_db.usage_records s
        WHERE s.id > ?
          AND NOT EXISTS (
              SELECT 1 FROM existing_keys k
              WHERE k.session_id = s.session_id AND k.message_uuid = s.message_uuid
          )
    """
    # Count locally instead of diffing remote COUNT(*) before/after; both
    # sides of the anti-join are client-side, so this costs no round trip.
    to_insert = conn.execute(f"SELECT COUNT(*) {anti_join}", [wm_id]).fetchone()[0]
    if to_insert > 0:
        conn.execute(f"INSERT INTO remote.usage_records ({_USAGE_COLS}) SELECT {_USAGE_COLS} {anti_join}", [wm_id])
    conn.execute("DROP TABLE existing_keys")
    return to_insert


def _push_model_pricing(conn: "duckdb.DuckDBPyConnection") -> None:
    """
    Anti-join INSERT of new model_pricing rows by model_name.

    Price updates to existing rows are not propagated until quack adds
    DELETE/UPSERT; pricing changes rarely and local stats use local pricing.
    """
    try:
        existing_models = [r[0] for r in conn.execute(
            "SELECT model_name FROM remote.model_pricing"
        ).fetchall()]
        if existing_models:
            conn.execute("CREATE OR REPLACE TEMP TABLE existing_models (model_name VARCHAR)")
            conn.executemany("INSERT INTO existing_models VALUES (?)", [(m,) for m in existing_models])
            conn.execute("""
                INSERT INTO remote.model_pricing
                SELECT s.* FROM local_db.model_pricing s
                WHERE NOT EXISTS (
                    SELECT 1 FROM existing_models e WHERE e.model_name = s.model_name
                )
            """)
            conn.execute("DROP TABLE existing_models")
        else:
            conn.execute("INSERT INTO remote.model_pricing SELECT * FROM local_db.model_pricing")
    except Exception:
        pass


def _push_limits(conn: "duckdb.DuckDBPyConnection") -> bool:
    """
    Anti-join INSERT of new limits_snapshots rows by timestamp.

    Returns:
        True if limits are fully pushed (or there was nothing to push);
        False on any failure so the limits watermark is not advanced
    """
    try:
        local_limits = conn.execute("SELECT COUNT(*) FROM local_db.limits_snapshots").fetchone()[0]
        if local_limits == 0:
            return True
        existing_ts = [r[0] for r in conn.execute(
            "SELECT timestamp FROM remote.limits_snapshots"
        ).fetchall()]
        if existing_ts:
            conn.execute("CREATE OR REPLACE TEMP TABLE existing_limits_ts (timestamp VARCHAR)")
            conn.executemany("INSERT INTO existing_limits_ts VALUES (?)", [(t,) for t in existing_ts])
            conn.execute("""
                INSERT INTO remote.limits_snapshots
                SELECT s.* FROM local_db.limits_snapshots s
                WHERE NOT EXISTS (
                    SELECT 1 FROM existing_limits_ts e WHERE e.timestamp = s.timestamp
                )
            """)
            conn.execute("DROP TABLE existing_limits_ts")
        else:
            conn.execute("INSERT INTO remote.limits_snapshots SELECT * FROM local_db.limits_snapshots")
        return True
    except Exception:
        return False


def push_to_remote(local_db_path: Path, full: bool = False) -> dict:
    """
    Push new local records to the remote, additively.

    Uses a local watermark (sync_state) to push only records inserted since
    the last successful push. With nothing new locally, returns without
    connecting to the remote at all. full=True forces the watermark-free
    anti-join push that reconciles any remote gaps.

    Returns:
        Dict with new_records, remote_total, devices, skipped
    """
    _require_duckdb()

    from src.storage.duckdb_backend import get_sync_state

    if get_sync_state(QUACK_PURGE_KEY, db_path=local_db_path) == "1":
        raise RuntimeError(
            "quack push blocked: a --rebuild rewrote local row identities and the "
            "remote still holds the old rows. Run: ccg sync repair (rebuilds the "
            "remote table from local truth, preserving other devices' rows), or "
            "purge this device's rows on the remote yourself and run: "
            "ccg sync push --quack-purged --full"
        )

    state = _read_local_push_state(local_db_path)
    wm_id = None if full else state["wm_id"]

    # A local max id below the watermark means the local db was rebuilt;
    # discard the watermark so the full anti-join reconciles from scratch.
    if wm_id is not None and (state["max_id"] or 0) < wm_id:
        wm_id = None

    new_usage = state["max_id"] is not None and (wm_id is None or state["max_id"] > wm_id)
    new_limits = state["max_limits_ts"] is not None and (
        full or state["wm_limits_ts"] is None or state["max_limits_ts"] > state["wm_limits_ts"]
    )

    if not new_usage and not new_limits and not full:
        return {"new_records": 0, "remote_total": None, "devices": None, "skipped": True}

    conn = connect_remote()
    incremental = False
    limits_ok = True
    new_records = 0
    remote_total = None
    devices = None
    try:
        init_remote_schema(conn)
        conn.execute(f"ATTACH '{local_db_path}' AS local_db (READ_ONLY)")

        before = conn.execute("SELECT COUNT(*) FROM remote.usage_records").fetchone()[0]

        if new_usage or full:
            if before == 0:
                # Empty remote (fresh server or restore): plain INSERT of
                # everything local, regardless of watermark.
                conn.execute(f"""
                    INSERT INTO remote.usage_records ({_USAGE_COLS})
                    SELECT {_USAGE_COLS} FROM local_db.usage_records
                """)
            elif wm_id is not None:
                try:
                    new_records = _push_usage_incremental(conn, wm_id)
                    incremental = True
                except Exception:
                    _push_usage_full(conn)
            else:
                _push_usage_full(conn)

        if new_limits:
            limits_ok = _push_limits(conn)

        # Remote-total/device reporting and pricing sync only off the hot
        # path: on an incremental push these remote scans cost more than
        # the insert itself.
        if not incremental:
            _push_model_pricing(conn)
            remote_total = conn.execute("SELECT COUNT(*) FROM remote.usage_records").fetchone()[0]
            new_records = remote_total - before
            devices = conn.execute(
                "SELECT COUNT(DISTINCT device_id) FROM remote.usage_records WHERE device_id IS NOT NULL"
            ).fetchone()[0]
    finally:
        conn.close()

    # Advance watermarks only after the remote connection is closed: its
    # READ_ONLY attach holds the local file open, and a concurrent writer
    # handle on the same file would conflict. Exceptions above propagate
    # before reaching here, so a failed push never advances a watermark.
    from src.storage.duckdb_backend import set_sync_state

    if state["max_id"] is not None:
        set_sync_state(WM_USAGE_KEY, str(state["max_id"]), db_path=local_db_path)
    if limits_ok and state["max_limits_ts"] is not None:
        set_sync_state(WM_LIMITS_KEY, state["max_limits_ts"], db_path=local_db_path)

    return {
        "new_records": new_records,
        "remote_total": remote_total,
        "devices": devices,
        "skipped": False,
    }


#endregion


#region Repair


def _remote_usage_columns(conn: "duckdb.DuckDBPyConnection") -> list[str]:
    """Column names of the live remote usage_records table."""
    cur = conn.execute("SELECT * FROM remote.usage_records LIMIT 0")
    return [d[0] for d in cur.description]


def _fetch_remote_usage_arrow(conn: "duckdb.DuckDBPyConnection"):
    """Materialize the entire remote usage_records table client-side."""
    result = conn.execute("SELECT * FROM remote.usage_records").arrow()
    # duckdb returns a RecordBatchReader on some versions, a Table on others
    return result.read_all() if hasattr(result, "read_all") else result


def repair_remote(local_db_path: Path) -> dict:
    """
    Rebuild the remote usage_records table without data loss after a local
    --rebuild rewrote row identities.

    Quack has no DELETE/ALTER, so replacing rows means recreating the table:

    1. Pull every remote row into a timestamped local backup DuckDB file
    2. Copy rows of devices this install is NOT authoritative for (device_id
       absent from the local db) into a timestamped server-side backup table
    3. DROP + recreate usage_records on the current schema
    4. Refill: all local rows (corrected identities) plus the preserved
       foreign-device rows
    5. Verify per-device counts, clear the purge guard, advance the watermark

    Foreign devices keep their rows byte-for-byte (still pre-fix counting
    until each of them rebuilds and repairs in turn). model_pricing is also
    recreated from local so schema additions propagate. Both backups outlive
    the repair; delete them manually once satisfied.

    Returns:
        Summary dict: backup_path, keep_table, per-device before/after counts

    Raises:
        RuntimeError: If post-repair verification fails (backups intact)
    """
    _require_duckdb()

    from src.storage.duckdb_backend import get_sync_state, set_sync_state

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = local_db_path.parent / f"quack-remote-backup-{stamp}.duckdb"

    conn = connect_remote()
    try:
        init_remote_schema(conn)
        conn.execute(f"ATTACH '{local_db_path}' AS local_db (READ_ONLY)")

        local_devices = {
            r[0] for r in conn.execute(
                "SELECT DISTINCT device_id FROM local_db.usage_records WHERE device_id IS NOT NULL"
            ).fetchall()
        }
        local_nulls = conn.execute(
            "SELECT COUNT(*) FROM local_db.usage_records WHERE device_id IS NULL"
        ).fetchone()[0]
        remote_nulls = conn.execute(
            "SELECT COUNT(*) FROM remote.usage_records WHERE device_id IS NULL"
        ).fetchone()[0]
        # NULL-device rows can't be attributed to an install: with rows on
        # both sides the refill would count the same usage twice
        if local_nulls and remote_nulls:
            raise RuntimeError(
                f"repair aborted: {local_nulls} local and {remote_nulls} remote rows have "
                "no device_id, so they cannot be told apart. Re-ingest with a configured "
                "device (ccg update usage --rebuild) before repairing."
            )
        remote_cols = _remote_usage_columns(conn)
        before = {
            r[0]: r[1] for r in conn.execute(
                "SELECT COALESCE(device_id, '<null>'), COUNT(*) FROM remote.usage_records GROUP BY 1"
            ).fetchall()
        }

        # 1. Full client-side backup of the remote table, as-is
        remote_rows = _fetch_remote_usage_arrow(conn)
        conn.execute(f"ATTACH '{backup_path}' AS bak")
        conn.register("remote_rows_arrow", remote_rows)
        conn.execute("CREATE TABLE bak.usage_records AS SELECT * FROM remote_rows_arrow")
        conn.execute("DETACH bak")

        # 2. Server-side backup table holding only foreign-device rows
        keep_table = f"usage_records_keep_{stamp}"
        col_list = ", ".join(remote_cols)
        conn.execute(f"CREATE TABLE remote.{keep_table} AS SELECT * FROM remote_rows_arrow LIMIT 0")
        keep_predicate = (
            "device_id IS NULL" if not local_devices else
            "device_id IS NULL OR device_id NOT IN ("
            + ", ".join(f"'{d}'" for d in sorted(local_devices)) + ")"
        )
        conn.execute(f"""
            INSERT INTO remote.{keep_table} ({col_list})
            SELECT {col_list} FROM remote_rows_arrow WHERE {keep_predicate}
        """)

        # 3. Recreate on the current schema
        conn.execute("DROP TABLE remote.usage_records")
        init_remote_schema(conn)

        # 4a. Corrected local rows
        conn.execute(f"""
            INSERT INTO remote.usage_records ({_USAGE_COLS})
            SELECT {_USAGE_COLS} FROM local_db.usage_records
        """)

        # 4b. Preserved foreign rows; columns the old schema lacked fill
        # with their defaults
        conn.execute(f"""
            INSERT INTO remote.usage_records ({col_list})
            SELECT {col_list} FROM remote_rows_arrow WHERE {keep_predicate}
        """)
        conn.unregister("remote_rows_arrow")

        # model_pricing: recreate positionally-aligned with local
        conn.execute("DROP TABLE remote.model_pricing")
        init_remote_schema(conn)
        conn.execute("INSERT INTO remote.model_pricing SELECT * FROM local_db.model_pricing")

        # 5. Verify: local devices match local counts, foreign match before
        local_counts = {
            r[0]: r[1] for r in conn.execute(
                "SELECT device_id, COUNT(*) FROM local_db.usage_records "
                "WHERE device_id IS NOT NULL GROUP BY 1"
            ).fetchall()
        }
        after = {
            r[0]: r[1] for r in conn.execute(
                "SELECT COALESCE(device_id, '<null>'), COUNT(*) FROM remote.usage_records GROUP BY 1"
            ).fetchall()
        }
        expected = dict(before)
        for device, count in local_counts.items():
            expected[device] = count
        if local_nulls:
            expected["<null>"] = local_nulls
        expected = {d: c for d, c in expected.items() if c}
        if after != expected:
            raise RuntimeError(
                f"repair verification failed: expected {expected}, remote has {after}. "
                f"Backups intact: {backup_path} (local) and remote.{keep_table} (server)"
            )

        max_id = conn.execute("SELECT MAX(id) FROM local_db.usage_records").fetchone()[0]
    finally:
        conn.close()

    # Same ordering rule as push_to_remote: touch local sync_state only after
    # the remote connection releases its READ_ONLY attach on the local file.
    if get_sync_state(QUACK_PURGE_KEY, db_path=local_db_path) == "1":
        set_sync_state(QUACK_PURGE_KEY, "0", db_path=local_db_path)
    if max_id is not None:
        set_sync_state(WM_USAGE_KEY, str(max_id), db_path=local_db_path)

    return {
        "backup_path": str(backup_path),
        "keep_table": keep_table,
        "local_devices": sorted(local_devices),
        "before": before,
        "after": after,
    }


#endregion


#region Read (for --remote flag)


def load_historical_records(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[UsageRecord]:
    conn = connect_remote()
    try:
        query = "SELECT * FROM remote.usage_records WHERE 1=1"
        params = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date, timestamp"

        result = conn.execute(query, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        records = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            token_usage = None
            if row_dict.get("input_tokens", 0) > 0 or row_dict.get("output_tokens", 0) > 0:
                token_usage = TokenUsage(
                    input_tokens=row_dict["input_tokens"],
                    output_tokens=row_dict["output_tokens"],
                    cache_creation_tokens=row_dict["cache_creation_tokens"],
                    cache_read_tokens=row_dict["cache_read_tokens"],
                )
            try:
                ts = datetime.fromisoformat(row_dict["timestamp"])
            except (ValueError, TypeError):
                continue
            records.append(UsageRecord(
                timestamp=ts,
                session_id=row_dict["session_id"],
                message_uuid=row_dict["message_uuid"],
                message_type=row_dict["message_type"],
                model=row_dict["model"],
                folder=row_dict["folder"],
                git_branch=row_dict["git_branch"],
                version=row_dict["version"],
                token_usage=token_usage,
            ))
        return records
    finally:
        conn.close()


def get_database_stats() -> dict:
    conn = connect_remote()
    try:
        total_records = conn.execute("SELECT COUNT(*) FROM remote.usage_records").fetchone()[0]
        total_days = conn.execute("SELECT COUNT(DISTINCT date) FROM remote.usage_records").fetchone()[0]

        if total_records == 0:
            return {
                "total_records": 0, "total_days": 0,
                "oldest_date": None, "newest_date": None, "newest_timestamp": None,
                "total_tokens": 0, "total_prompts": 0, "total_responses": 0,
                "total_sessions": 0, "tokens_by_model": {}, "cost_by_model": {},
                "total_cost": 0.0, "avg_tokens_per_session": 0,
                "avg_tokens_per_response": 0, "avg_cost_per_session": 0.0,
                "avg_cost_per_response": 0.0,
            }

        date_range = conn.execute("SELECT MIN(date), MAX(date) FROM remote.usage_records").fetchone()
        oldest_date, newest_date = date_range

        # Aggregate directly from usage_records -- remote daily_snapshots is
        # left empty because quack lacks DELETE/ON CONFLICT for upserts.
        newest_timestamp = conn.execute(
            "SELECT MAX(timestamp) FROM remote.usage_records"
        ).fetchone()[0]

        agg = conn.execute("""
            SELECT
                SUM(total_tokens),
                SUM(CASE WHEN message_type = 'user' THEN 1 ELSE 0 END),
                SUM(CASE WHEN message_type = 'assistant' THEN 1 ELSE 0 END),
                COUNT(DISTINCT session_id)
            FROM remote.usage_records
        """).fetchone()
        total_tokens = agg[0] or 0
        total_prompts = agg[1] or 0
        total_responses = agg[2] or 0
        total_sessions = agg[3] or 0

        tokens_by_model = {}
        model_rows = conn.execute("""
            SELECT model, SUM(total_tokens) as tokens
            FROM remote.usage_records WHERE model IS NOT NULL
            GROUP BY model ORDER BY tokens DESC
        """).fetchall()
        tokens_by_model = {r[0]: r[1] for r in model_rows if r[0]}

        total_cost = 0.0
        cost_by_model = {}
        try:
            cost_rows = conn.execute("""
                SELECT ur.model,
                    SUM(ur.input_tokens), SUM(ur.output_tokens),
                    SUM(ur.cache_creation_tokens), SUM(ur.cache_read_tokens),
                    mp.input_price_per_mtok, mp.output_price_per_mtok,
                    mp.cache_write_price_per_mtok, mp.cache_read_price_per_mtok,
                    SUM(COALESCE(ur.cache_creation_1h_tokens, 0)),
                    mp.cache_write_1h_price_per_mtok
                FROM remote.usage_records ur
                LEFT JOIN remote.model_pricing mp ON ur.model = mp.model_name
                WHERE ur.model IS NOT NULL
                GROUP BY ur.model, mp.input_price_per_mtok, mp.output_price_per_mtok,
                         mp.cache_write_price_per_mtok, mp.cache_read_price_per_mtok,
                         mp.cache_write_1h_price_per_mtok
            """).fetchall()
            for row in cost_rows:
                write_1h_price = row[10] if row[10] is not None else (row[7] or 0) * 1.6
                model_cost = (
                    ((row[1] or 0) / 1_000_000) * (row[5] or 0) +
                    ((row[2] or 0) / 1_000_000) * (row[6] or 0) +
                    (((row[3] or 0) - (row[9] or 0)) / 1_000_000) * (row[7] or 0) +
                    ((row[9] or 0) / 1_000_000) * write_1h_price +
                    ((row[4] or 0) / 1_000_000) * (row[8] or 0)
                )
                cost_by_model[row[0]] = model_cost
                total_cost += model_cost
        except Exception:
            pass

        return {
            "total_records": total_records,
            "total_days": total_days,
            "oldest_date": oldest_date,
            "newest_date": newest_date,
            "newest_timestamp": newest_timestamp,
            "total_tokens": total_tokens,
            "total_prompts": total_prompts,
            "total_responses": total_responses,
            "total_sessions": total_sessions,
            "tokens_by_model": tokens_by_model,
            "cost_by_model": cost_by_model,
            "total_cost": total_cost,
            "avg_tokens_per_session": round(total_tokens / total_sessions) if total_sessions else 0,
            "avg_tokens_per_response": round(total_tokens / total_responses) if total_responses else 0,
            "avg_cost_per_session": round(total_cost / total_sessions, 2) if total_sessions else 0.0,
            "avg_cost_per_response": round(total_cost / total_responses, 4) if total_responses else 0.0,
        }
    finally:
        conn.close()


def get_latest_limits() -> dict | None:
    conn = connect_remote()
    try:
        row = conn.execute("""
            SELECT session_pct, week_pct, opus_pct,
                   session_reset, week_reset, opus_reset
            FROM remote.limits_snapshots
            ORDER BY timestamp DESC LIMIT 1
        """).fetchone()
        if not row:
            return None
        return {
            "session_pct": row[0] or 0, "week_pct": row[1] or 0,
            "opus_pct": row[2] or 0, "session_reset": row[3] or "",
            "week_reset": row[4] or "", "opus_reset": row[5] or "",
        }
    finally:
        conn.close()


#endregion
