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
from typing import Optional

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

from src.config.user_config import get_sync_config, get_sync_provider
from src.models.usage_record import UsageRecord, TokenUsage
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
    config = get_sync_config()
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
    config = get_sync_config()
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS remote.usage_records (
            id INTEGER PRIMARY KEY,
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
            device_id VARCHAR,
            device_name VARCHAR,
            device_type VARCHAR,
            UNIQUE(session_id, message_uuid)
        )
    """)
    conn.execute("CREATE SEQUENCE IF NOT EXISTS remote.usage_records_id_seq START 1")
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
            notes VARCHAR
        )
    """)


#endregion


#region Push


def push_to_remote(local_db_path: Path) -> dict:
    _require_duckdb()
    conn = connect_remote()

    try:
        init_remote_schema(conn)
        conn.execute(f"ATTACH '{local_db_path}' AS local_db (READ_ONLY)")

        before = conn.execute("SELECT COUNT(*) FROM remote.usage_records").fetchone()[0]

        conn.execute("""
            INSERT INTO remote.usage_records (
                date, timestamp, session_id, message_uuid, message_type,
                model, folder, git_branch, version,
                input_tokens, output_tokens,
                cache_creation_tokens, cache_read_tokens, total_tokens,
                device_id, device_name, device_type
            )
            SELECT
                date, timestamp, session_id, message_uuid, message_type,
                model, folder, git_branch, version,
                input_tokens, output_tokens,
                cache_creation_tokens, cache_read_tokens, total_tokens,
                device_id, device_name, device_type
            FROM local_db.usage_records
            ON CONFLICT (session_id, message_uuid) DO NOTHING
        """)

        after = conn.execute("SELECT COUNT(*) FROM remote.usage_records").fetchone()[0]
        new_records = after - before

        # Rebuild snapshots only for dates in the pushed batch
        _rebuild_remote_snapshots(conn, local_conn_name="local_db")

        # Push model_pricing
        try:
            conn.execute("""
                INSERT INTO remote.model_pricing
                SELECT * FROM local_db.model_pricing
                ON CONFLICT (model_name) DO UPDATE SET
                    input_price_per_mtok = excluded.input_price_per_mtok,
                    output_price_per_mtok = excluded.output_price_per_mtok,
                    cache_write_price_per_mtok = excluded.cache_write_price_per_mtok,
                    cache_read_price_per_mtok = excluded.cache_read_price_per_mtok,
                    last_updated = excluded.last_updated,
                    notes = excluded.notes
            """)
        except Exception:
            pass

        # Push limits_snapshots
        try:
            local_limits = conn.execute("SELECT COUNT(*) FROM local_db.limits_snapshots").fetchone()[0]
            if local_limits > 0:
                conn.execute("""
                    INSERT INTO remote.limits_snapshots
                    SELECT * FROM local_db.limits_snapshots
                    ON CONFLICT (timestamp) DO NOTHING
                """)
        except Exception:
            pass

        remote_total = conn.execute("SELECT COUNT(*) FROM remote.usage_records").fetchone()[0]
        devices = conn.execute(
            "SELECT COUNT(DISTINCT device_id) FROM remote.usage_records WHERE device_id IS NOT NULL"
        ).fetchone()[0]

        return {
            "new_records": new_records,
            "remote_total": remote_total,
            "devices": devices,
        }
    finally:
        conn.close()


def _rebuild_remote_snapshots(conn: "duckdb.DuckDBPyConnection", local_conn_name: str = "local_db") -> None:
    timestamp = datetime.now().isoformat()
    conn.execute(f"""
        INSERT INTO remote.daily_snapshots
        SELECT
            date,
            SUM(CASE WHEN message_type = 'user' THEN 1 ELSE 0 END),
            SUM(CASE WHEN message_type = 'assistant' THEN 1 ELSE 0 END),
            COUNT(DISTINCT session_id),
            SUM(total_tokens),
            SUM(input_tokens),
            SUM(output_tokens),
            SUM(cache_creation_tokens),
            SUM(cache_read_tokens),
            ?,
            NULL, NULL, NULL
        FROM remote.usage_records
        WHERE date IN (SELECT DISTINCT date FROM {local_conn_name}.usage_records)
        GROUP BY date
        ON CONFLICT (date) DO UPDATE SET
            total_prompts = excluded.total_prompts,
            total_responses = excluded.total_responses,
            total_sessions = excluded.total_sessions,
            total_tokens = excluded.total_tokens,
            input_tokens = excluded.input_tokens,
            output_tokens = excluded.output_tokens,
            cache_creation_tokens = excluded.cache_creation_tokens,
            cache_read_tokens = excluded.cache_read_tokens,
            snapshot_timestamp = excluded.snapshot_timestamp
    """, [timestamp])


#endregion


#region Read (for --remote flag)


def load_historical_records(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
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

        newest_timestamp = conn.execute(
            "SELECT MAX(snapshot_timestamp) FROM remote.daily_snapshots"
        ).fetchone()[0]

        agg = conn.execute("""
            SELECT SUM(total_tokens), SUM(total_prompts),
                   SUM(total_responses), SUM(total_sessions)
            FROM remote.daily_snapshots
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
                    mp.cache_write_price_per_mtok, mp.cache_read_price_per_mtok
                FROM remote.usage_records ur
                LEFT JOIN remote.model_pricing mp ON ur.model = mp.model_name
                WHERE ur.model IS NOT NULL
                GROUP BY ur.model, mp.input_price_per_mtok, mp.output_price_per_mtok,
                         mp.cache_write_price_per_mtok, mp.cache_read_price_per_mtok
            """).fetchall()
            for row in cost_rows:
                model_cost = (
                    ((row[1] or 0) / 1_000_000) * (row[5] or 0) +
                    ((row[2] or 0) / 1_000_000) * (row[6] or 0) +
                    ((row[3] or 0) / 1_000_000) * (row[7] or 0) +
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


def get_latest_limits() -> Optional[dict]:
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
