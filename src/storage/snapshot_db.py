#region Imports
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from src.models.usage_record import UsageRecord

#endregion


#region Constants
DEFAULT_DB_PATH = Path.home() / ".claude" / "usage" / "usage_history.db"
DEVICE_COLUMNS = ["device_id", "device_name", "device_type"]
#endregion


#region Helper Functions


def load_model_pricing() -> list[tuple]:
    """
    Load model pricing from JSON file with hardcoded fallback.

    Reads pricing data from src/data/model_pricing.json if available,
    otherwise falls back to hardcoded defaults.

    Returns:
        List of tuples: (model_name, input_price, output_price, cache_write, cache_read, notes)
    """
    # Hardcoded fallback pricing
    fallback_pricing = [
        ('claude-opus-4-5-20251101', 15.00, 75.00, 18.75, 1.50, 30.00, 'Claude Opus 4.5'),
        ('claude-opus-4-1-20250805', 15.00, 75.00, 18.75, 1.50, 30.00, 'Claude Opus 4.1'),
        ('claude-sonnet-4-5-20250929', 3.00, 15.00, 3.75, 0.30, 6.00, 'Claude Sonnet 4.5'),
        ('claude-sonnet-4-20250514', 3.00, 15.00, 3.75, 0.30, 6.00, 'Claude Sonnet 4'),
        ('claude-haiku-4-5-20251001', 1.00, 5.00, 1.25, 0.10, 2.00, 'Claude Haiku 4.5'),
        ('claude-haiku-3-5-20241022', 0.80, 4.00, 1.00, 0.08, 1.60, 'Claude 3.5 Haiku'),
        ('claude-sonnet-3-7-20250219', 3.00, 15.00, 3.75, 0.30, 6.00, 'Claude Sonnet 3.7'),
        ('claude-opus-4-20250514', 15.00, 75.00, 18.75, 1.50, 30.00, 'Claude Opus 4'),
        ('<synthetic>', 0.00, 0.00, 0.00, 0.00, 0.00, 'Test/synthetic model'),
    ]

    try:
        # Try to load from JSON file
        json_path = Path(__file__).parent.parent / "data" / "model_pricing.json"
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)

            pricing = []
            for model_name, model_data in data.get("models", {}).items():
                cache_write = model_data.get("cache_write_per_mtok", 0.0)
                pricing.append((
                    model_name,
                    model_data.get("input_per_mtok", 0.0),
                    model_data.get("output_per_mtok", 0.0),
                    cache_write,
                    model_data.get("cache_read_per_mtok", 0.0),
                    model_data.get("cache_write_1h_per_mtok", round(cache_write * 1.6, 4)),
                    model_data.get("notes", ""),
                ))
            return pricing if pricing else fallback_pricing
    except (json.JSONDecodeError, KeyError, OSError):
        pass

    return fallback_pricing


def _add_device_columns_if_missing(cursor: sqlite3.Cursor, table_name: str) -> None:
    """
    Add device metadata columns to a table if they don't exist.

    Used for migrating existing databases to support multi-device sync.

    Args:
        cursor: SQLite cursor
        table_name: Name of the table to modify
    """
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cursor.fetchall()}

    for col in DEVICE_COLUMNS:
        if col not in existing_columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} TEXT")


#endregion


#region Functions


def init_database(db_path: Path = DEFAULT_DB_PATH) -> None:
    """
    Initialize the SQLite database for historical snapshots.

    Creates tables if they don't exist:
    - daily_snapshots: Daily aggregated usage data
    - usage_records: Individual usage records for detailed analysis

    Args:
        db_path: Path to the SQLite database file

    Raises:
        sqlite3.Error: If database initialization fails
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Table for daily aggregated snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_snapshots (
                date TEXT PRIMARY KEY,
                total_prompts INTEGER NOT NULL,
                total_responses INTEGER NOT NULL,
                total_sessions INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cache_creation_tokens INTEGER NOT NULL,
                cache_read_tokens INTEGER NOT NULL,
                snapshot_timestamp TEXT NOT NULL,
                device_id TEXT,
                device_name TEXT,
                device_type TEXT
            )
        """)

        # Add device columns if they don't exist (for migration)
        _add_device_columns_if_missing(cursor, "daily_snapshots")

        # Table for detailed usage records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                message_uuid TEXT NOT NULL,
                message_type TEXT NOT NULL,
                model TEXT,
                folder TEXT NOT NULL,
                git_branch TEXT,
                version TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cache_creation_tokens INTEGER NOT NULL,
                cache_read_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                cache_creation_1h_tokens INTEGER DEFAULT 0,
                device_id TEXT,
                device_name TEXT,
                device_type TEXT,
                UNIQUE(session_id, message_uuid)
            )
        """)

        # Add device columns if they don't exist (for migration)
        _add_device_columns_if_missing(cursor, "usage_records")

        # 1h cache-write split (bills at 2x base input vs 1.25x for 5m)
        cursor.execute("PRAGMA table_info(usage_records)")
        if "cache_creation_1h_tokens" not in {row[1] for row in cursor.fetchall()}:
            cursor.execute(
                "ALTER TABLE usage_records ADD COLUMN cache_creation_1h_tokens INTEGER DEFAULT 0"
            )

        # Index for faster date-based queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_records_date
            ON usage_records(date)
        """)

        # Table for usage limits snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS limits_snapshots (
                timestamp TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                session_pct INTEGER,
                week_pct INTEGER,
                opus_pct INTEGER,
                session_reset TEXT,
                week_reset TEXT,
                opus_reset TEXT,
                device_id TEXT,
                device_name TEXT,
                device_type TEXT
            )
        """)

        # Add device columns if they don't exist (for migration)
        _add_device_columns_if_missing(cursor, "limits_snapshots")

        # Index for faster date-based queries on limits
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_limits_snapshots_date
            ON limits_snapshots(date)
        """)

        # Table for tracking JSONL file metadata (for incremental parsing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_metadata (
                file_path TEXT PRIMARY KEY,
                mtime_ns INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                record_count INTEGER NOT NULL,
                last_parsed TEXT NOT NULL
            )
        """)

        # Table for model pricing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_pricing (
                model_name TEXT PRIMARY KEY,
                input_price_per_mtok REAL NOT NULL,
                output_price_per_mtok REAL NOT NULL,
                cache_write_price_per_mtok REAL NOT NULL,
                cache_read_price_per_mtok REAL NOT NULL,
                last_updated TEXT NOT NULL,
                notes TEXT,
                cache_write_1h_price_per_mtok REAL
            )
        """)

        # Per-file aggregate contributions ledger (aggregate storage mode):
        # what each transcript file last added to daily_snapshots, so a
        # reparse of a grown file applies only the delta instead of re-adding
        # the whole file.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_contributions (
                file_path TEXT NOT NULL,
                date TEXT NOT NULL,
                prompts INTEGER NOT NULL,
                responses INTEGER NOT NULL,
                sessions INTEGER NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cache_creation_tokens INTEGER NOT NULL,
                cache_read_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                PRIMARY KEY (file_path, date)
            )
        """)

        cursor.execute("PRAGMA table_info(model_pricing)")
        if "cache_write_1h_price_per_mtok" not in {row[1] for row in cursor.fetchall()}:
            cursor.execute(
                "ALTER TABLE model_pricing ADD COLUMN cache_write_1h_price_per_mtok REAL"
            )

        # Populate pricing data from JSON file (with fallback)
        pricing_data = load_model_pricing()

        timestamp = datetime.now().isoformat()
        for model_name, input_price, output_price, cache_write, cache_read, cache_write_1h, notes in pricing_data:
            cursor.execute("""
                INSERT OR REPLACE INTO model_pricing (
                    model_name, input_price_per_mtok, output_price_per_mtok,
                    cache_write_price_per_mtok, cache_read_price_per_mtok,
                    cache_write_1h_price_per_mtok, last_updated, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (model_name, input_price, output_price, cache_write, cache_read, cache_write_1h, timestamp, notes))

        conn.commit()
    finally:
        conn.close()


def save_snapshot(
    records: list[UsageRecord],
    db_path: Path = DEFAULT_DB_PATH,
    storage_mode: str = "aggregate",
    device_id: str | None = None,
    device_name: str | None = None,
    device_type: str | None = None,
) -> int:
    """
    Save usage records to the database as a snapshot.

    Only saves records that don't already exist (based on session_id + message_uuid).
    Also updates daily_snapshots table with aggregated data.

    Args:
        records: List of usage records to save
        db_path: Path to the SQLite database file
        storage_mode: "aggregate" (daily totals only) or "full" (individual records)
        device_id: Device identifier for multi-device sync
        device_name: Human-readable device name
        device_type: Device type (macos, windows, linux)

    Returns:
        Number of new records saved

    Raises:
        sqlite3.Error: If database operation fails
    """
    if not records:
        return 0

    init_database(db_path)

    conn = sqlite3.connect(db_path)
    saved_count = 0

    try:
        cursor = conn.cursor()

        # Save individual records only if in "full" mode
        if storage_mode == "full":
            for record in records:
                # Get token values (0 for user messages without token_usage)
                input_tokens = record.token_usage.input_tokens if record.token_usage else 0
                output_tokens = record.token_usage.output_tokens if record.token_usage else 0
                cache_creation_tokens = record.token_usage.cache_creation_tokens if record.token_usage else 0
                cache_read_tokens = record.token_usage.cache_read_tokens if record.token_usage else 0
                total_tokens = record.token_usage.total_tokens if record.token_usage else 0
                cache_creation_1h = record.token_usage.cache_creation_1h_tokens if record.token_usage else 0

                # Assistant rows dedupe GLOBALLY on the billed-response id
                # (session forks replay identical responses under new session
                # ids); user rows stay session-scoped. An existing row with
                # smaller usage upgrades in place (mid-stream partial
                # capture), never downgrades.
                if record.message_type == "assistant":
                    cursor.execute(
                        "SELECT id, total_tokens FROM usage_records "
                        "WHERE message_uuid = ? AND message_type = 'assistant'",
                        (record.message_uuid,),
                    )
                else:
                    cursor.execute(
                        "SELECT id, total_tokens FROM usage_records "
                        "WHERE session_id = ? AND message_uuid = ?",
                        (record.session_id, record.message_uuid),
                    )
                existing = cursor.fetchone()
                if existing is not None:
                    if record.message_type == "assistant" and total_tokens > (existing[1] or 0):
                        cursor.execute("""
                            UPDATE usage_records
                            SET timestamp = ?, input_tokens = ?, output_tokens = ?,
                                cache_creation_tokens = ?, cache_read_tokens = ?,
                                total_tokens = ?, cache_creation_1h_tokens = ?
                            WHERE id = ?
                        """, (
                            record.timestamp.isoformat(),
                            input_tokens, output_tokens,
                            cache_creation_tokens, cache_read_tokens,
                            total_tokens, cache_creation_1h, existing[0],
                        ))
                    continue

                try:
                    cursor.execute("""
                        INSERT INTO usage_records (
                            date, timestamp, session_id, message_uuid, message_type,
                            model, folder, git_branch, version,
                            input_tokens, output_tokens,
                            cache_creation_tokens, cache_read_tokens, total_tokens,
                            cache_creation_1h_tokens,
                            device_id, device_name, device_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.date_key,
                        record.timestamp.isoformat(),
                        record.session_id,
                        record.message_uuid,
                        record.message_type,
                        record.model,
                        record.folder,
                        record.git_branch,
                        record.version,
                        input_tokens,
                        output_tokens,
                        cache_creation_tokens,
                        cache_read_tokens,
                        total_tokens,
                        cache_creation_1h,
                        device_id,
                        device_name,
                        device_type,
                    ))
                    saved_count += 1
                except sqlite3.IntegrityError:
                    # Same key inserted concurrently between check and insert
                    pass

        # Update daily snapshots (aggregate by date)
        if storage_mode == "full":
            # In full mode, only update dates that have records in usage_records
            # IMPORTANT: Never use REPLACE - it would delete old data when JSONL files age out
            # Instead, recalculate only for dates that currently have records
            timestamp = datetime.now().isoformat()

            # Get all dates that currently have usage_records
            cursor.execute("SELECT DISTINCT date FROM usage_records")
            dates_with_records = [row[0] for row in cursor.fetchall()]

            for date in dates_with_records:
                # Calculate totals for this date from usage_records
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN message_type = 'user' THEN 1 ELSE 0 END) as total_prompts,
                        SUM(CASE WHEN message_type = 'assistant' THEN 1 ELSE 0 END) as total_responses,
                        COUNT(DISTINCT session_id) as total_sessions,
                        SUM(total_tokens) as total_tokens,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens,
                        SUM(cache_creation_tokens) as cache_creation_tokens,
                        SUM(cache_read_tokens) as cache_read_tokens
                    FROM usage_records
                    WHERE date = ?
                """, (date,))

                row = cursor.fetchone()

                # Use INSERT OR REPLACE only for dates that currently have data
                # This preserves historical daily_snapshots for dates no longer in usage_records
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_snapshots (
                        date, total_prompts, total_responses, total_sessions, total_tokens,
                        input_tokens, output_tokens, cache_creation_tokens,
                        cache_read_tokens, snapshot_timestamp,
                        device_id, device_name, device_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date,
                    row[0] or 0,
                    row[1] or 0,
                    row[2] or 0,
                    row[3] or 0,
                    row[4] or 0,
                    row[5] or 0,
                    row[6] or 0,
                    row[7] or 0,
                    timestamp,
                    device_id,
                    device_name,
                    device_type,
                ))
        else:
            # In aggregate mode, compute from incoming records
            from collections import defaultdict
            daily_aggregates = defaultdict(lambda: {
                "prompts": 0,
                "responses": 0,
                "sessions": set(),
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
                "total_tokens": 0,
            })

            for record in records:
                date_key = record.date_key
                daily_aggregates[date_key]["sessions"].add(record.session_id)

                # Count message types
                if record.is_user_prompt:
                    daily_aggregates[date_key]["prompts"] += 1
                elif record.is_assistant_response:
                    daily_aggregates[date_key]["responses"] += 1

                # Token usage only on assistant messages
                if record.token_usage:
                    daily_aggregates[date_key]["input_tokens"] += record.token_usage.input_tokens
                    daily_aggregates[date_key]["output_tokens"] += record.token_usage.output_tokens
                    daily_aggregates[date_key]["cache_creation_tokens"] += record.token_usage.cache_creation_tokens
                    daily_aggregates[date_key]["cache_read_tokens"] += record.token_usage.cache_read_tokens
                    daily_aggregates[date_key]["total_tokens"] += record.token_usage.total_tokens

            # Insert or update daily snapshots
            timestamp = datetime.now().isoformat()
            for date_key, agg in daily_aggregates.items():
                # Get existing data for this date to merge with new data
                cursor.execute("""
                    SELECT total_prompts, total_responses, total_sessions, total_tokens,
                           input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens
                    FROM daily_snapshots WHERE date = ?
                """, (date_key,))
                existing = cursor.fetchone()

                if existing:
                    # Merge with existing (add to existing totals)
                    cursor.execute("""
                        INSERT OR REPLACE INTO daily_snapshots (
                            date, total_prompts, total_responses, total_sessions, total_tokens,
                            input_tokens, output_tokens, cache_creation_tokens,
                            cache_read_tokens, snapshot_timestamp,
                            device_id, device_name, device_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        date_key,
                        existing[0] + agg["prompts"],
                        existing[1] + agg["responses"],
                        existing[2] + len(agg["sessions"]),
                        existing[3] + agg["total_tokens"],
                        existing[4] + agg["input_tokens"],
                        existing[5] + agg["output_tokens"],
                        existing[6] + agg["cache_creation_tokens"],
                        existing[7] + agg["cache_read_tokens"],
                        timestamp,
                        device_id,
                        device_name,
                        device_type,
                    ))
                else:
                    # New date, insert fresh
                    cursor.execute("""
                        INSERT INTO daily_snapshots (
                            date, total_prompts, total_responses, total_sessions, total_tokens,
                            input_tokens, output_tokens, cache_creation_tokens,
                            cache_read_tokens, snapshot_timestamp,
                            device_id, device_name, device_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        date_key,
                        agg["prompts"],
                        agg["responses"],
                        len(agg["sessions"]),
                        agg["total_tokens"],
                        agg["input_tokens"],
                        agg["output_tokens"],
                        agg["cache_creation_tokens"],
                        agg["cache_read_tokens"],
                        timestamp,
                        device_id,
                        device_name,
                        device_type,
                    ))
                saved_count += 1

        conn.commit()
    finally:
        conn.close()

    return saved_count


def save_file_aggregate(
    file_path: Path,
    records: list[UsageRecord],
    db_path: Path = DEFAULT_DB_PATH,
    device_id: str | None = None,
    device_name: str | None = None,
    device_type: str | None = None,
) -> int:
    """
    Apply one transcript file's aggregate contribution as a DELTA.

    Computes the file's fresh per-date sums, subtracts what the ledger says
    the file previously contributed, applies the difference to
    daily_snapshots, and stores the fresh sums back. A file already tracked
    in file_metadata but absent from the ledger was parsed under the old
    add-everything logic: its transition parse contributes zero so
    pre-ledger totals are never re-added.

    Returns:
        Number of assistant responses newly accounted for (delta)
    """
    from src.storage.duckdb_backend import _CONTRIB_FIELDS, _aggregate_by_date

    init_database(db_path)
    fresh = _aggregate_by_date(records)

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT date, {', '.join(_CONTRIB_FIELDS)} FROM file_contributions WHERE file_path = ?",
            (str(file_path),),
        )
        previous = {row[0]: dict(zip(_CONTRIB_FIELDS, row[1:])) for row in cursor.fetchall()}
        if not previous:
            cursor.execute(
                "SELECT 1 FROM file_metadata WHERE file_path = ?", (str(file_path),)
            )
            if cursor.fetchone() is not None:
                previous = {date: dict(day) for date, day in fresh.items()}

        timestamp = datetime.now().isoformat()
        new_responses = 0
        for date, day in fresh.items():
            prev = previous.get(date, dict.fromkeys(_CONTRIB_FIELDS, 0))
            delta = {field: day[field] - prev[field] for field in _CONTRIB_FIELDS}
            new_responses += max(delta["responses"], 0)
            if any(delta.values()):
                cursor.execute(
                    """
                    SELECT total_prompts, total_responses, total_sessions,
                           input_tokens, output_tokens, cache_creation_tokens,
                           cache_read_tokens
                    FROM daily_snapshots WHERE date = ?
                    """,
                    (date,),
                )
                base = cursor.fetchone() or (0, 0, 0, 0, 0, 0, 0)
                merged = [
                    max(base[0] + delta["prompts"], 0),
                    max(base[1] + delta["responses"], 0),
                    max(base[2] + delta["sessions"], 0),
                    max(base[3] + delta["input_tokens"], 0),
                    max(base[4] + delta["output_tokens"], 0),
                    max(base[5] + delta["cache_creation_tokens"], 0),
                    max(base[6] + delta["cache_read_tokens"], 0),
                ]
                total = merged[3] + merged[4] + merged[5] + merged[6]
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO daily_snapshots (
                        date, total_prompts, total_responses, total_sessions,
                        total_tokens, input_tokens, output_tokens,
                        cache_creation_tokens, cache_read_tokens,
                        snapshot_timestamp, device_id, device_name, device_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (date, merged[0], merged[1], merged[2], total,
                     merged[3], merged[4], merged[5], merged[6],
                     timestamp, device_id, device_name, device_type),
                )

        cursor.execute("DELETE FROM file_contributions WHERE file_path = ?", (str(file_path),))
        for date, day in fresh.items():
            cursor.execute(
                f"""
                INSERT INTO file_contributions (file_path, date, {', '.join(_CONTRIB_FIELDS)})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple([str(file_path), date] + [day[field] for field in _CONTRIB_FIELDS]),
            )
        conn.commit()
        return new_responses
    finally:
        conn.close()


def save_limits_snapshot(
    session_pct: int,
    week_pct: int,
    opus_pct: int,
    session_reset: str,
    week_reset: str,
    opus_reset: str,
    db_path: Path = DEFAULT_DB_PATH,
    device_id: str | None = None,
    device_name: str | None = None,
    device_type: str | None = None,
) -> None:
    """
    Save usage limits snapshot to the database.

    Args:
        session_pct: Session usage percentage
        week_pct: Week (all models) usage percentage
        opus_pct: Opus usage percentage
        session_reset: Session reset time
        week_reset: Week reset time
        opus_reset: Opus reset time
        db_path: Path to the SQLite database file
        device_id: Device identifier for multi-device sync
        device_name: Human-readable device name
        device_type: Device type (macos, windows, linux)

    Raises:
        sqlite3.Error: If database operation fails
    """
    init_database(db_path)

    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        date = datetime.now().strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT OR REPLACE INTO limits_snapshots (
                timestamp, date, session_pct, week_pct, opus_pct,
                session_reset, week_reset, opus_reset,
                device_id, device_name, device_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            date,
            session_pct,
            week_pct,
            opus_pct,
            session_reset,
            week_reset,
            opus_reset,
            device_id,
            device_name,
            device_type,
        ))

        conn.commit()
    finally:
        conn.close()


def load_historical_records(
    start_date: str | None = None,
    end_date: str | None = None,
    db_path: Path = DEFAULT_DB_PATH
) -> list[UsageRecord]:
    """
    Load historical usage records from the database.

    Supports both storage modes:
    - Full mode: Loads individual records from usage_records table
    - Aggregate mode: Loads daily summaries from daily_snapshots and converts to synthetic records

    Args:
        start_date: Optional start date in YYYY-MM-DD format (inclusive)
        end_date: Optional end date in YYYY-MM-DD format (inclusive)
        db_path: Path to the SQLite database file

    Returns:
        List of UsageRecord objects

    Raises:
        sqlite3.Error: If database query fails
    """
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()

        # First try to load from usage_records (full mode)
        query = "SELECT * FROM usage_records WHERE 1=1"
        params = []

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date, timestamp"

        cursor.execute(query, params)

        records = []
        for row in cursor.fetchall():
            # Parse the row into a UsageRecord
            # Row columns: id, date, timestamp, session_id, message_uuid, message_type,
            #              model, folder, git_branch, version,
            #              input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, total_tokens
            from src.models.usage_record import TokenUsage

            # Only create TokenUsage if tokens exist (assistant messages)
            token_usage = None
            if row[10] > 0 or row[11] > 0:  # if input_tokens or output_tokens exist
                token_usage = TokenUsage(
                    input_tokens=row[10],
                    output_tokens=row[11],
                    cache_creation_tokens=row[12],
                    cache_read_tokens=row[13],
                )

            record = UsageRecord(
                timestamp=datetime.fromisoformat(row[2]),
                session_id=row[3],
                message_uuid=row[4],
                message_type=row[5],
                model=row[6],
                folder=row[7],
                git_branch=row[8],
                version=row[9],
                token_usage=token_usage,
            )
            records.append(record)

        # If no records from usage_records, try daily_snapshots (aggregate mode)
        if not records:
            records = _load_from_daily_snapshots(cursor, start_date, end_date)

        return records
    finally:
        conn.close()


def _load_from_daily_snapshots(
    cursor: sqlite3.Cursor,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[UsageRecord]:
    """
    Load records from daily_snapshots table and convert to synthetic UsageRecord objects.

    Used when storage mode is 'aggregate' and usage_records is empty.

    Args:
        cursor: SQLite cursor
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of synthetic UsageRecord objects (one per day)
    """
    from src.models.usage_record import TokenUsage

    query = "SELECT date, total_tokens, input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, total_sessions FROM daily_snapshots WHERE 1=1"
    params = []

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += " ORDER BY date"

    cursor.execute(query, params)

    records = []
    for row in cursor.fetchall():
        date_str, total_tokens, input_tokens, output_tokens, cache_creation, cache_read, sessions = row

        # Create a synthetic UsageRecord for each day
        token_usage = TokenUsage(
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            cache_creation_tokens=cache_creation or 0,
            cache_read_tokens=cache_read or 0,
        )

        record = UsageRecord(
            timestamp=datetime.fromisoformat(f"{date_str}T12:00:00"),
            session_id=f"daily-{date_str}",
            message_uuid=f"aggregate-{date_str}",
            message_type="assistant",
            model="aggregate",
            folder="aggregate",
            git_branch=None,
            version=None,
            token_usage=token_usage,
        )
        records.append(record)

    return records


def get_text_analysis_stats(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """
    Analyze message content from JSONL files for text statistics.

    Returns:
        Dictionary with text analysis statistics
    """
    from src.config.settings import get_claude_jsonl_files
    from src.data.jsonl_parser import parse_all_jsonl_files
    from src.utils.text_analysis import (
        count_absolutely_right_phrases,
        count_perfect_phrases,
        count_please_phrases,
        count_swears,
        count_thank_phrases,
    )

    try:
        # Get current JSONL files
        jsonl_files = get_claude_jsonl_files()
        if not jsonl_files:
            return {
                "user_swears": 0,
                "assistant_swears": 0,
                "perfect_count": 0,
                "absolutely_right_count": 0,
                "user_thanks": 0,
                "user_please": 0,
                "avg_user_prompt_chars": 0,
                "total_user_chars": 0,
            }

        # Parse all records
        records = parse_all_jsonl_files(jsonl_files)

        user_swears = 0
        assistant_swears = 0
        perfect_count = 0
        absolutely_right_count = 0
        user_thanks = 0
        user_please = 0
        total_user_chars = 0
        user_prompt_count = 0

        for record in records:
            if not record.content:
                continue

            if record.is_user_prompt:
                user_swears += count_swears(record.content)
                user_thanks += count_thank_phrases(record.content)
                user_please += count_please_phrases(record.content)
                total_user_chars += record.char_count
                user_prompt_count += 1
            elif record.is_assistant_response:
                assistant_swears += count_swears(record.content)
                perfect_count += count_perfect_phrases(record.content)
                absolutely_right_count += count_absolutely_right_phrases(record.content)

        avg_user_prompt_chars = total_user_chars / user_prompt_count if user_prompt_count > 0 else 0

        return {
            "user_swears": user_swears,
            "assistant_swears": assistant_swears,
            "perfect_count": perfect_count,
            "absolutely_right_count": absolutely_right_count,
            "user_thanks": user_thanks,
            "user_please": user_please,
            "avg_user_prompt_chars": round(avg_user_prompt_chars),
            "total_user_chars": total_user_chars,
        }
    except Exception:
        # Return zeros if analysis fails
        return {
            "user_swears": 0,
            "assistant_swears": 0,
            "perfect_count": 0,
            "absolutely_right_count": 0,
            "user_thanks": 0,
            "user_please": 0,
            "avg_user_prompt_chars": 0,
            "total_user_chars": 0,
        }


def get_limits_data(db_path: Path = DEFAULT_DB_PATH) -> dict[str, dict[str, int]]:
    """
    Get daily maximum limits percentages from the database.

    Backfills missing days with the maximum value from the next earliest day
    that has data, since usage limits accumulate over time and don't decrease
    within a period.

    Returns a dictionary mapping dates to their max limits:
    {
        "2025-10-11": {"week_pct": 14, "opus_pct": 8},
        ...
    }

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Dictionary mapping dates to max week_pct and opus_pct for that day
    """
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()

        # Get max week_pct and opus_pct per day
        cursor.execute("""
            SELECT
                date,
                MAX(week_pct) as max_week,
                MAX(opus_pct) as max_opus
            FROM limits_snapshots
            GROUP BY date
            ORDER BY date
        """)

        # First, get all the raw data
        raw_data = {}
        dates = []
        for row in cursor.fetchall():
            date = row[0]
            dates.append(date)
            raw_data[date] = {
                "week_pct": row[1] or 0,
                "opus_pct": row[2] or 0
            }

        # If no data, return empty
        if not dates:
            return {}

        # Create a complete date range from earliest to latest
        from datetime import datetime, timedelta
        start_date = datetime.strptime(min(dates), "%Y-%m-%d")
        end_date = datetime.strptime(max(dates), "%Y-%m-%d")

        # Build the result with backfilling
        result = {}
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")

            if date_str in raw_data:
                # We have data for this day
                result[date_str] = raw_data[date_str]
            else:
                # Missing day - backfill with the max from the next earliest day with data
                # Look forward to find the next day with data
                next_date = current_date + timedelta(days=1)
                found_data = None

                while next_date <= end_date:
                    next_date_str = next_date.strftime("%Y-%m-%d")
                    if next_date_str in raw_data:
                        found_data = raw_data[next_date_str]
                        break
                    next_date += timedelta(days=1)

                if found_data:
                    # Use the next available data
                    result[date_str] = found_data
                else:
                    # No future data found, use the last known value
                    # Look backward for the most recent data
                    prev_date = current_date - timedelta(days=1)
                    while prev_date >= start_date:
                        prev_date_str = prev_date.strftime("%Y-%m-%d")
                        if prev_date_str in result:
                            result[date_str] = result[prev_date_str]
                            break
                        prev_date -= timedelta(days=1)

                    # If still no data found (shouldn't happen), use zeros
                    if date_str not in result:
                        result[date_str] = {"week_pct": 0, "opus_pct": 0}

            current_date += timedelta(days=1)

        return result
    finally:
        conn.close()


def get_latest_limits(db_path: Path = DEFAULT_DB_PATH) -> dict | None:
    """
    Get the most recent limits snapshot from the database.

    Returns a dictionary with the latest limits data:
    {
        "session_pct": 14,
        "week_pct": 18,
        "opus_pct": 8,
        "session_reset": "Oct 16, 10:59am (Europe/Brussels)",
        "week_reset": "Oct 18, 3pm (Europe/Brussels)",
        "opus_reset": "Oct 18, 3pm (Europe/Brussels)",
    }

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Dictionary with latest limits, or None if no data exists
    """
    if not db_path.exists():
        return None

    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()

        # Get most recent limits snapshot
        cursor.execute("""
            SELECT session_pct, week_pct, opus_pct,
                   session_reset, week_reset, opus_reset
            FROM limits_snapshots
            ORDER BY timestamp DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "session_pct": row[0] or 0,
            "week_pct": row[1] or 0,
            "opus_pct": row[2] or 0,
            "session_reset": row[3] or "",
            "week_reset": row[4] or "",
            "opus_reset": row[5] or "",
        }
    finally:
        conn.close()


def get_database_stats(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """
    Get statistics about the historical database.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Dictionary with statistics including:
        - total_records, total_days, oldest_date, newest_date, newest_timestamp
        - total_tokens, total_prompts, total_sessions
        - tokens_by_model: dict of model -> token count
        - avg_tokens_per_session, avg_tokens_per_prompt
    """
    if not db_path.exists():
        return {
            "total_records": 0,
            "total_days": 0,
            "oldest_date": None,
            "newest_date": None,
            "newest_timestamp": None,
            "total_tokens": 0,
            "total_prompts": 0,
            "total_responses": 0,
            "total_sessions": 0,
            "tokens_by_model": {},
            "cost_by_model": {},
            "total_cost": 0.0,
            "avg_tokens_per_session": 0,
            "avg_tokens_per_response": 0,
            "avg_cost_per_session": 0.0,
            "avg_cost_per_response": 0.0,
        }

    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()

        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM usage_records")
        total_records = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT date) FROM usage_records")
        total_days = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(date), MAX(date) FROM usage_records")
        oldest_date, newest_date = cursor.fetchone()

        # Get newest snapshot timestamp
        cursor.execute("SELECT MAX(snapshot_timestamp) FROM daily_snapshots")
        newest_timestamp = cursor.fetchone()[0]

        # Aggregate statistics from daily_snapshots
        cursor.execute("""
            SELECT
                SUM(total_tokens) as total_tokens,
                SUM(total_prompts) as total_prompts,
                SUM(total_responses) as total_responses,
                SUM(total_sessions) as total_sessions
            FROM daily_snapshots
        """)
        row = cursor.fetchone()
        total_tokens = row[0] or 0
        total_prompts = row[1] or 0
        total_responses = row[2] or 0
        total_sessions = row[3] or 0

        # Tokens by model (only available if usage_records exist)
        tokens_by_model = {}
        if total_records > 0:
            cursor.execute("""
                SELECT model, SUM(total_tokens) as tokens
                FROM usage_records
                GROUP BY model
                ORDER BY tokens DESC
            """)
            tokens_by_model = {row[0]: row[1] for row in cursor.fetchall() if row[0]}

        # Calculate costs by joining with pricing table
        total_cost = 0.0
        cost_by_model = {}

        if total_records > 0:
            cursor.execute("""
                SELECT
                    ur.model,
                    SUM(ur.input_tokens) as total_input,
                    SUM(ur.output_tokens) as total_output,
                    SUM(ur.cache_creation_tokens) as total_cache_write,
                    SUM(ur.cache_read_tokens) as total_cache_read,
                    mp.input_price_per_mtok,
                    mp.output_price_per_mtok,
                    mp.cache_write_price_per_mtok,
                    mp.cache_read_price_per_mtok,
                    SUM(COALESCE(ur.cache_creation_1h_tokens, 0)) as total_cache_write_1h,
                    mp.cache_write_1h_price_per_mtok
                FROM usage_records ur
                LEFT JOIN model_pricing mp ON ur.model = mp.model_name
                WHERE ur.model IS NOT NULL
                GROUP BY ur.model
            """)

            for row in cursor.fetchall():
                model = row[0]
                input_tokens = row[1] or 0
                output_tokens = row[2] or 0
                cache_write_tokens = row[3] or 0
                cache_read_tokens = row[4] or 0
                cache_write_1h_tokens = row[9] or 0

                # Pricing per million tokens; 1h cache writes bill at 2x base
                # input (vs 1.25x for the 5m tier)
                input_price = row[5] or 0.0
                output_price = row[6] or 0.0
                cache_write_price = row[7] or 0.0
                cache_read_price = row[8] or 0.0
                cache_write_1h_price = row[10] if row[10] is not None else cache_write_price * 1.6

                # Calculate cost in dollars
                model_cost = (
                    (input_tokens / 1_000_000) * input_price +
                    (output_tokens / 1_000_000) * output_price +
                    ((cache_write_tokens - cache_write_1h_tokens) / 1_000_000) * cache_write_price +
                    (cache_write_1h_tokens / 1_000_000) * cache_write_1h_price +
                    (cache_read_tokens / 1_000_000) * cache_read_price
                )

                cost_by_model[model] = model_cost
                total_cost += model_cost

        # Calculate averages
        avg_tokens_per_session = total_tokens / total_sessions if total_sessions > 0 else 0
        avg_tokens_per_response = total_tokens / total_responses if total_responses > 0 else 0
        avg_cost_per_session = total_cost / total_sessions if total_sessions > 0 else 0
        avg_cost_per_response = total_cost / total_responses if total_responses > 0 else 0

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
            "avg_tokens_per_session": round(avg_tokens_per_session),
            "avg_tokens_per_response": round(avg_tokens_per_response),
            "avg_cost_per_session": round(avg_cost_per_session, 2),
            "avg_cost_per_response": round(avg_cost_per_response, 4),
        }
    finally:
        conn.close()


def get_stale_files(
    all_files: list[Path],
    db_path: Path = DEFAULT_DB_PATH
) -> tuple[list[Path], list[str]]:
    """
    Identify which JSONL files need to be re-parsed based on mtime/size changes.

    Compares current file stats against stored metadata to find:
    - New files (not in database)
    - Modified files (mtime or size changed)
    - Deleted files (in database but not on disk)

    Args:
        all_files: List of all JSONL file paths on disk
        db_path: Path to the SQLite database file

    Returns:
        Tuple of (stale_files, deleted_file_paths):
        - stale_files: List of Path objects that need re-parsing
        - deleted_file_paths: List of file path strings that were deleted
    """
    if not db_path.exists():
        # No database yet, all files are stale
        return (all_files, [])

    init_database(db_path)

    conn = sqlite3.connect(db_path)
    stale_files = []
    deleted_files = []

    try:
        cursor = conn.cursor()

        # Get all stored file metadata
        cursor.execute("SELECT file_path, mtime_ns, size_bytes FROM file_metadata")
        stored_metadata = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        # Convert current files to set of path strings for comparison
        current_file_paths = {str(f) for f in all_files}

        # Check each current file
        for file_path in all_files:
            path_str = str(file_path)
            try:
                stat = file_path.stat()
                current_mtime_ns = stat.st_mtime_ns
                current_size = stat.st_size

                if path_str not in stored_metadata:
                    # New file
                    stale_files.append(file_path)
                else:
                    stored_mtime_ns, stored_size = stored_metadata[path_str]
                    if current_mtime_ns != stored_mtime_ns or current_size != stored_size:
                        # Modified file
                        stale_files.append(file_path)
            except OSError:
                # File inaccessible, skip
                continue

        # Find deleted files (in DB but not on disk)
        for stored_path in stored_metadata.keys():
            if stored_path not in current_file_paths:
                deleted_files.append(stored_path)

        return (stale_files, deleted_files)
    finally:
        conn.close()


def update_files_metadata(
    file_paths: list[Path],
    record_count: int = 0,
    db_path: Path = DEFAULT_DB_PATH,
    stats: dict[str, tuple[int, int]] | None = None,
) -> None:
    """
    Upsert parse metadata for many files in a single connection.

    Files that fail to stat are skipped.

    Args:
        file_paths: Paths to the JSONL files
        record_count: Number of records parsed from each file
        db_path: Path to the SQLite database file
    """
    if not file_paths:
        return

    init_database(db_path)

    timestamp = datetime.now().isoformat()
    rows = []
    for file_path in file_paths:
        pre = (stats or {}).get(str(file_path))
        if pre is not None:
            mtime_ns, size_bytes = pre
        else:
            try:
                stat = file_path.stat()
            except OSError:
                continue
            mtime_ns, size_bytes = stat.st_mtime_ns, stat.st_size
        rows.append((str(file_path), mtime_ns, size_bytes, record_count, timestamp))

    if not rows:
        return

    conn = sqlite3.connect(db_path)
    try:
        conn.executemany("""
            INSERT OR REPLACE INTO file_metadata (
                file_path, mtime_ns, size_bytes, record_count, last_parsed
            ) VALUES (?, ?, ?, ?, ?)
        """, rows)
        conn.commit()
    finally:
        conn.close()


def remove_deleted_file_metadata(
    deleted_paths: list[str],
    db_path: Path = DEFAULT_DB_PATH
) -> None:
    """
    Remove metadata for files that no longer exist.

    Args:
        deleted_paths: List of file path strings to remove
        db_path: Path to the SQLite database file
    """
    if not deleted_paths:
        return

    if not db_path.exists():
        return

    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()

        for path in deleted_paths:
            cursor.execute("DELETE FROM file_metadata WHERE file_path = ?", (path,))

        conn.commit()
    finally:
        conn.close()


def get_update_coverage(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """
    Get record count and date bounds of usage_records.

    Cheap alternative to get_database_stats for flows that only need
    coverage, not token/cost aggregates.

    Returns:
        Dict with total_records, oldest_date, newest_date
    """
    if not db_path.exists():
        return {"total_records": 0, "oldest_date": None, "newest_date": None}

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM usage_records"
        ).fetchone()
        return {"total_records": row[0] or 0, "oldest_date": row[1], "newest_date": row[2]}
    finally:
        conn.close()


def get_file_metadata_count(db_path: Path = DEFAULT_DB_PATH) -> int:
    """
    Get the count of files tracked in file_metadata table.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Number of files tracked
    """
    if not db_path.exists():
        return 0

    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM file_metadata")
        return cursor.fetchone()[0]
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return 0
    finally:
        conn.close()


def fill_empty_daily_snapshots(
    start_date: str,
    end_date: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """
    Insert zero-usage daily_snapshots rows for any date in [start_date, end_date]
    that does not already have a row. Returns the number of rows inserted.
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    init_database(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT date FROM daily_snapshots")
        existing = {row[0] for row in cursor.fetchall()}

        current = _dt.strptime(start_date, "%Y-%m-%d").date()
        last = _dt.strptime(end_date, "%Y-%m-%d").date()
        timestamp = _dt.now().isoformat()
        inserted = 0
        while current <= last:
            date_str = current.strftime("%Y-%m-%d")
            if date_str not in existing:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO daily_snapshots (
                        date, total_prompts, total_responses, total_sessions, total_tokens,
                        input_tokens, output_tokens, cache_creation_tokens,
                        cache_read_tokens, snapshot_timestamp
                    ) VALUES (?, 0, 0, 0, 0, 0, 0, 0, 0, ?)
                    """,
                    (date_str, timestamp),
                )
                inserted += 1
            current += _td(days=1)
        conn.commit()
        return inserted
    finally:
        conn.close()
#endregion
