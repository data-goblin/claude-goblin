"""
OneLake Delta sync sink for Claude Goblin.

Pushes usage data to Delta tables in a Microsoft Fabric lakehouse via
delta-rs, keeping the quack sink's watermark-incremental semantics. Only
aggregates leave the machine: the lakehouse gets daily per-device per-model
token totals, never message-grain rows (no session ids, folder paths, or
branches). Auth reuses the machine's `az login` session (bearer token in
memory only, never on disk).
"""
#region Imports
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import pyarrow as pa
    from deltalake import DeltaTable, write_deltalake
    from deltalake.exceptions import CommitFailedError, DeltaError, TableNotFoundError
    DELTALAKE_AVAILABLE = True
except ImportError:
    DELTALAKE_AVAILABLE = False

from src.config.user_config import get_device_accounts, get_sync_config

#endregion


#region Constants

# sync_state keys on the local db; separate from quack's so sinks advance
# independently
WM_USAGE_KEY = "last_pushed_usage_id_onelake"
WM_LIMITS_KEY = "last_pushed_limits_ts_onelake"
LAST_PUSH_KEY = "last_onelake_push_at"
PUSH_COUNT_KEY = "onelake_push_count"

_ONELAKE_HOST = "onelake.dfs.fabric.microsoft.com"
_STORAGE_RESOURCE = "https://storage.azure.com"
_POWERBI_RESOURCE = "https://analysis.windows.net/powerbi/api"
_MERGE_ATTEMPTS = 3
_DEFAULT_PUSH_INTERVAL = 900
_DEFAULT_COMPACT_EVERY = 50
_VACUUM_RETENTION_HOURS = 168

# Full-day re-aggregation per (date, device, model, folder, branch):
# incremental pushes recompute every affected day's totals so the merge's
# update replaces rows with correct absolutes rather than partial increments.
# NULL dimensions coalesce to '' so merge predicates match on re-push.
_USAGE_DAILY_SELECT = """
    SELECT
        CAST(date AS DATE) AS date,
        device_id,
        COALESCE(model, '<none>') AS model,
        COALESCE(folder, '') AS folder,
        COALESCE(git_branch, '') AS git_branch,
        CAST(COUNT(*) AS BIGINT) AS records,
        CAST(COUNT(DISTINCT session_id) AS BIGINT) AS sessions,
        CAST(SUM(input_tokens) AS BIGINT) AS input_tokens,
        CAST(SUM(output_tokens) AS BIGINT) AS output_tokens,
        CAST(SUM(cache_creation_tokens) AS BIGINT) AS cache_creation_tokens,
        CAST(SUM(COALESCE(cache_creation_1h_tokens, 0)) AS BIGINT) AS cache_creation_1h_tokens,
        CAST(SUM(cache_read_tokens) AS BIGINT) AS cache_read_tokens,
        CAST(SUM(total_tokens) AS BIGINT) AS total_tokens
    FROM usage_records
"""

_LIMITS_SELECT = """
    SELECT
        CAST(timestamp AS TIMESTAMPTZ) AS timestamp,
        CAST(date AS DATE) AS date,
        session_pct, week_pct, opus_pct,
        session_reset, week_reset, opus_reset,
        device_id, device_name, device_type
    FROM limits_snapshots
"""

#endregion


#region Helpers


def _require_deltalake() -> None:
    if not DELTALAKE_AVAILABLE:
        raise ImportError("deltalake not installed. Install with: uv pip install 'claude-goblin[onelake]'")


def _get_onelake_config() -> dict[str, Any]:
    """Validated onelake sync config; raises RuntimeError when unconfigured."""
    config = get_sync_config("onelake")
    if not config.get("workspace_id") or not config.get("lakehouse_id"):
        raise RuntimeError(
            "onelake sync is not configured (missing workspace_id/lakehouse_id). "
            "Run: ccg sync setup --provider onelake"
        )
    return config


def _get_az_token(resource: str, tenant_id: str | None) -> str:
    """
    Mint a bearer token for `resource` off the current az login session.

    The token stays in memory; the tenant pin avoids minting against whatever
    tenant happens to be the ambient az default on multi-tenant machines.
    """
    # Resolve the executable so Windows finds az.cmd (bare names skip
    # PATHEXT resolution under CreateProcess).
    az = shutil.which("az")
    if az is None:
        raise RuntimeError("az CLI not found on PATH. Install Azure CLI and run: az login")
    args = [az, "account", "get-access-token", "--resource", resource,
            "--query", "accessToken", "-o", "tsv"]
    if tenant_id:
        args += ["--tenant", tenant_id]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        tenant_hint = f" --tenant {tenant_id}" if tenant_id else ""
        raise RuntimeError(
            f"Could not mint a token for {resource}. "
            f"Run: az login{tenant_hint} (stderr: {result.stderr.strip()[:200]})"
        )
    return result.stdout.strip()


def _table_uri(config: dict[str, Any], table: str) -> str:
    return (
        f"abfss://{config['workspace_id']}@{_ONELAKE_HOST}/"
        f"{config['lakehouse_id']}/Tables/{table}"
    )


def _read_push_state(local_db_path: Path, device_filter: list[str] | None) -> dict[str, Any]:
    """
    Device-filtered watermarks and maxima.

    The filter scopes the new-data gate itself, so activity from excluded
    devices never triggers a network call.
    """
    import duckdb

    from src.storage.duckdb_backend import get_sync_state

    where, params = _device_where(device_filter)
    conn = duckdb.connect(str(local_db_path), read_only=True)
    try:
        try:
            row = conn.execute(
                f"SELECT MAX(id) FROM usage_records WHERE 1=1 {where}", params
            ).fetchone()
            max_id = row[0] if row else None
        except duckdb.Error:
            max_id = None
        try:
            row = conn.execute(
                f"SELECT MAX(timestamp) FROM limits_snapshots WHERE 1=1 {where}", params
            ).fetchone()
            max_limits_ts = row[0] if row else None
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


def _device_where(device_filter: list[str] | None) -> tuple[str, list[str]]:
    if not device_filter:
        return "", []
    placeholders = ", ".join("?" for _ in device_filter)
    return f"AND device_id IN ({placeholders})", list(device_filter)


def _upsert(
    uri: str,
    batch: "pa.Table",
    predicate: str,
    storage_options: dict[str, str],
    update_matched: bool = False,
) -> int:
    """
    Merge `batch` into the Delta table at `uri`, creating it on first push.

    Only TableNotFoundError routes to the create path (mode="error", never
    overwrite), so a transient failure can't be misread as table-missing.
    Commit conflicts from concurrent pushers retry with backoff.

    Returns:
        Rows inserted (batch size on create, merge metrics otherwise)
    """
    try:
        table = DeltaTable(uri, storage_options=storage_options)
    except TableNotFoundError:
        try:
            write_deltalake(uri, batch, mode="error", storage_options=storage_options)
            return int(batch.num_rows)
        except DeltaError as exc:
            # Lost the create race to a concurrent pusher: open and merge.
            if "already exists" not in str(exc).lower():
                raise
            table = DeltaTable(uri, storage_options=storage_options)

    last_error: Exception = RuntimeError("unreachable")
    for attempt in range(_MERGE_ATTEMPTS):
        try:
            merger = table.merge(batch, predicate, source_alias="s", target_alias="t")
            if update_matched:
                merger = merger.when_matched_update_all()
            merger = merger.when_not_matched_insert_all()
            metrics = merger.execute()
            inserted = metrics.get("num_target_rows_inserted", 0)
            return int(inserted) if isinstance(inserted, (int, float)) else 0
        except CommitFailedError as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise last_error


def _fetch_batches(
    local_db_path: Path,
    wm_id: int | None,
    device_filter: list[str] | None,
    accounts: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Read the outgoing daily-aggregate/pricing/devices/limits Arrow batches."""
    import duckdb

    where, params = _device_where(device_filter)
    conn = duckdb.connect(str(local_db_path), read_only=True)
    try:
        usage_sql = f"{_USAGE_DAILY_SELECT} WHERE 1=1 {where}"
        usage_params = list(params)
        new_underlying = 0
        if wm_id is not None:
            # Incremental: re-aggregate only days that gained rows.
            usage_sql += (
                f" AND date IN (SELECT DISTINCT date FROM usage_records WHERE id > ? {where})"
            )
            usage_params += [str(wm_id), *params]
            row = conn.execute(
                f"SELECT COUNT(*) FROM usage_records WHERE id > ? {where}",
                [str(wm_id), *params],
            ).fetchone()
            new_underlying = int(row[0]) if row else 0
        else:
            row = conn.execute(
                f"SELECT COUNT(*) FROM usage_records WHERE 1=1 {where}", params
            ).fetchone()
            new_underlying = int(row[0]) if row else 0
        usage_sql += " GROUP BY 1, 2, 3, 4, 5 ORDER BY 1, 2, 3, 4, 5"
        usage = conn.execute(usage_sql, usage_params).to_arrow_table()

        pricing = conn.execute("SELECT * FROM model_pricing").to_arrow_table()

        device_rows = conn.execute(
            f"SELECT DISTINCT device_id, device_name, device_type FROM usage_records WHERE 1=1 {where}",
            params,
        ).fetchall()

        limits = None
        try:
            limits = conn.execute(f"{_LIMITS_SELECT} WHERE 1=1 {where}", params).to_arrow_table()
        except duckdb.Error:
            pass
    finally:
        conn.close()

    now = datetime.now(timezone.utc)
    usage = usage.append_column(
        "last_updated", pa.array([now] * usage.num_rows, type=pa.timestamp("us", tz="UTC"))
    )
    devices = pa.table({
        "device_id": [r[0] for r in device_rows],
        "device_name": [r[1] for r in device_rows],
        "device_type": [r[2] for r in device_rows],
        "user_upn": [accounts.get(r[0], {}).get("email") for r in device_rows],
        "organization": [accounts.get(r[0], {}).get("organization") for r in device_rows],
        "subscription": [accounts.get(r[0], {}).get("subscription") for r in device_rows],
        "last_push_at": pa.array([now] * len(device_rows), type=pa.timestamp("us", tz="UTC")),
    })

    return {
        "usage": usage,
        "pricing": pricing,
        "devices": devices,
        "limits": limits,
        "new_underlying": new_underlying,
    }


def _maybe_compact(
    tables: dict[str, Optional["DeltaTable"]],
    push_count: int,
    compact_every: int,
) -> None:
    """
    Compact + vacuum churn-heavy tables every `compact_every` pushes.

    Vacuum keeps delta-rs's retention guard at its default so files a
    not-yet-reframed Direct Lake model may still reference are never deleted.
    """
    if compact_every < 1 or push_count % compact_every != 0:
        return
    for table in tables.values():
        if table is None:
            continue
        try:
            table.optimize.compact()
            table.vacuum(retention_hours=_VACUUM_RETENTION_HOURS, dry_run=False)
        except Exception:
            pass


def _trigger_reframe(config: dict[str, Any]) -> None:
    """
    Ask the Direct Lake semantic model to reframe after new data landed.

    Best-effort: failures (throttling, missing permissions) never affect the
    push result.
    """
    model_id = config.get("semantic_model_id")
    workspace_id = config.get("workspace_id")
    if not model_id or not workspace_id:
        return
    try:
        token = _get_az_token(_POWERBI_RESOURCE, config.get("tenant_id"))
        request = urllib.request.Request(
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{model_id}/refreshes",
            data=json.dumps({"type": "full", "commitMode": "transactional"}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=30)
    except (RuntimeError, urllib.error.URLError, OSError):
        pass


#endregion


#region Push


def push_to_onelake(
    local_db_path: Path,
    full: bool = False,
    respect_interval: bool = True,
) -> dict[str, Any]:
    """
    Push new local records to the Fabric lakehouse Delta tables.

    Watermark-incremental like the quack sink, with the new-data gate scoped
    to the configured device_filter so excluded devices' activity never opens
    a connection. respect_interval=True (hook path) additionally no-ops
    inside min_push_interval seconds of the previous push.

    Returns:
        Dict with new_records, remote_total, devices, skipped
    """
    _require_deltalake()
    config = _get_onelake_config()

    from src.storage.duckdb_backend import get_sync_state, set_sync_state

    skipped = {"new_records": 0, "remote_total": None, "devices": None, "skipped": True}

    if respect_interval:
        interval = int(config.get("min_push_interval", _DEFAULT_PUSH_INTERVAL))
        last_raw = get_sync_state(LAST_PUSH_KEY, db_path=local_db_path)
        if last_raw is not None and (time.time() - float(last_raw)) < interval:
            return skipped

    device_filter_raw = config.get("device_filter")
    device_filter = list(device_filter_raw) if device_filter_raw else None

    state = _read_push_state(local_db_path, device_filter)
    wm_id = None if full else state["wm_id"]

    # A filtered max below the watermark means the local db was rebuilt;
    # discard the watermark so the merge reconciles everything.
    if wm_id is not None and (state["max_id"] or 0) < wm_id:
        wm_id = None

    new_usage = state["max_id"] is not None and (wm_id is None or state["max_id"] > wm_id)
    new_limits = state["max_limits_ts"] is not None and (
        full or state["wm_limits_ts"] is None or state["max_limits_ts"] > state["wm_limits_ts"]
    )
    if not new_usage and not new_limits and not full:
        return skipped

    token = _get_az_token(_STORAGE_RESOURCE, config.get("tenant_id"))
    storage_options = {"bearer_token": token, "use_fabric_endpoint": "true"}

    batches = _fetch_batches(local_db_path, wm_id, device_filter, get_device_accounts())

    new_records = 0
    if new_usage or full:
        _upsert(
            _table_uri(config, "usage_daily"),
            batches["usage"],
            "s.date = t.date AND s.device_id = t.device_id AND s.model = t.model"
            " AND s.folder = t.folder AND s.git_branch = t.git_branch",
            storage_options,
            update_matched=True,
        )
        new_records = int(batches["new_underlying"])
    set_sync_state(WM_USAGE_KEY, str(state["max_id"]), db_path=local_db_path)

    # Sidecar tables never block the usage push nor its watermark.
    limits_ok = True
    if new_limits and batches["limits"] is not None and batches["limits"].num_rows > 0:
        try:
            _upsert(
                _table_uri(config, "limits_snapshots"),
                batches["limits"],
                "s.timestamp = t.timestamp AND s.device_id = t.device_id",
                storage_options,
            )
        except Exception:
            limits_ok = False
    if limits_ok and state["max_limits_ts"] is not None:
        set_sync_state(WM_LIMITS_KEY, state["max_limits_ts"], db_path=local_db_path)

    try:
        _upsert(
            _table_uri(config, "model_pricing"),
            batches["pricing"],
            "s.model_name = t.model_name",
            storage_options,
            update_matched=True,
        )
    except Exception:
        pass

    try:
        if batches["devices"].num_rows > 0:
            _upsert(
                _table_uri(config, "devices"),
                batches["devices"],
                "s.device_id = t.device_id",
                storage_options,
                update_matched=True,
            )
    except Exception:
        pass

    set_sync_state(LAST_PUSH_KEY, str(int(time.time())), db_path=local_db_path)
    count_raw = get_sync_state(PUSH_COUNT_KEY, db_path=local_db_path)
    push_count = (int(count_raw) if count_raw is not None else 0) + 1
    set_sync_state(PUSH_COUNT_KEY, str(push_count), db_path=local_db_path)

    compact_every = int(config.get("compact_every", _DEFAULT_COMPACT_EVERY))
    if compact_every > 0 and push_count % compact_every == 0:
        handles: dict[str, DeltaTable | None] = {}
        for name in ("usage_daily", "devices"):
            try:
                handles[name] = DeltaTable(_table_uri(config, name), storage_options=storage_options)
            except Exception:
                handles[name] = None
        _maybe_compact(handles, push_count, compact_every)

    if new_records > 0:
        _trigger_reframe(config)

    return {
        "new_records": new_records,
        "remote_total": None,
        "devices": None,
        "skipped": False,
    }


#endregion
