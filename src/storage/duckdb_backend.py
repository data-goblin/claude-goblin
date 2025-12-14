"""
DuckDB storage backend for Claude Goblin.

Mirrors the snapshot_db.py API but uses DuckDB for storage.
Required for MotherDuck cloud sync and analytical queries.
"""
#region Imports
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

from src.models.usage_record import UsageRecord, TokenUsage
#endregion


#region Constants
DEFAULT_DB_PATH = Path.home() / ".claude" / "usage" / "usage_history.duckdb"
#endregion


#region Utility Functions


def is_duckdb_available() -> bool:
    """Check if DuckDB is installed."""
    return DUCKDB_AVAILABLE


def require_duckdb() -> None:
    """Raise an error if DuckDB is not available."""
    if not DUCKDB_AVAILABLE:
        raise ImportError(
            "DuckDB is not installed. Install with: uv pip install duckdb "
            "or: uv pip install claude-goblin[duckdb]"
        )


#endregion


#region Database Functions


def init_database(db_path: Path = DEFAULT_DB_PATH) -> None:
    """
    Initialize the DuckDB database for historical snapshots.

    Creates tables if they don't exist:
    - daily_snapshots: Daily aggregated usage data
    - usage_records: Individual usage records for detailed analysis
    - limits_snapshots: Usage limits history
    - file_metadata: JSONL file tracking for incremental parsing
    - model_pricing: Model pricing information

    Args:
        db_path: Path to the DuckDB database file

    Raises:
        ImportError: If DuckDB is not installed
        duckdb.Error: If database initialization fails
    """
    require_duckdb()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    try:
        # Table for daily aggregated snapshots
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_snapshots (
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

        # Table for detailed usage records
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_records (
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

        # Create sequence for auto-increment if not exists
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS usage_records_id_seq START 1
        """)

        # Index for faster date-based queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_records_date
            ON usage_records(date)
        """)

        # Table for usage limits snapshots
        conn.execute("""
            CREATE TABLE IF NOT EXISTS limits_snapshots (
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

        # Index for faster date-based queries on limits
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_limits_snapshots_date
            ON limits_snapshots(date)
        """)

        # Table for tracking JSONL file metadata (for incremental parsing)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_metadata (
                file_path VARCHAR PRIMARY KEY,
                mtime_ns BIGINT NOT NULL,
                size_bytes BIGINT NOT NULL,
                record_count INTEGER NOT NULL,
                last_parsed VARCHAR NOT NULL
            )
        """)

        # Table for model pricing
        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_pricing (
                model_name VARCHAR PRIMARY KEY,
                input_price_per_mtok DOUBLE NOT NULL,
                output_price_per_mtok DOUBLE NOT NULL,
                cache_write_price_per_mtok DOUBLE NOT NULL,
                cache_read_price_per_mtok DOUBLE NOT NULL,
                last_updated VARCHAR NOT NULL,
                notes VARCHAR
            )
        """)

        # Populate pricing data for known models
        pricing_data = [
            ('claude-opus-4-1-20250805', 15.00, 75.00, 18.75, 1.50, 'Current flagship model'),
            ('claude-sonnet-4-5-20250929', 3.00, 15.00, 3.75, 0.30, 'Current balanced model'),
            ('claude-haiku-4-5-20251001', 1.00, 5.00, 1.25, 0.10, 'Claude Haiku 4.5'),
            ('claude-haiku-3-5-20241022', 0.80, 4.00, 1.00, 0.08, 'Claude 3.5 Haiku'),
            ('claude-sonnet-4-20250514', 3.00, 15.00, 3.75, 0.30, 'Legacy Sonnet 4'),
            ('claude-opus-4-20250514', 15.00, 75.00, 18.75, 1.50, 'Legacy Opus 4'),
            ('claude-sonnet-3-7-20250219', 3.00, 15.00, 3.75, 0.30, 'Legacy Sonnet 3.7'),
            ('<synthetic>', 0.00, 0.00, 0.00, 0.00, 'Test/synthetic model'),
        ]

        timestamp = datetime.now().isoformat()
        for model_name, input_price, output_price, cache_write, cache_read, notes in pricing_data:
            conn.execute("""
                INSERT OR REPLACE INTO model_pricing (
                    model_name, input_price_per_mtok, output_price_per_mtok,
                    cache_write_price_per_mtok, cache_read_price_per_mtok,
                    last_updated, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [model_name, input_price, output_price, cache_write, cache_read, timestamp, notes])

    finally:
        conn.close()


def save_snapshot(
    records: list[UsageRecord],
    db_path: Path = DEFAULT_DB_PATH,
    storage_mode: str = "aggregate",
    device_id: Optional[str] = None,
    device_name: Optional[str] = None,
    device_type: Optional[str] = None,
) -> int:
    """
    Save usage records to the DuckDB database as a snapshot.

    Args:
        records: List of usage records to save
        db_path: Path to the DuckDB database file
        storage_mode: "aggregate" (daily totals only) or "full" (individual records)
        device_id: Device identifier for multi-device sync
        device_name: Human-readable device name
        device_type: Device type (macos, windows, linux)

    Returns:
        Number of new records saved

    Raises:
        duckdb.Error: If database operation fails
    """
    require_duckdb()

    if not records:
        return 0

    init_database(db_path)

    conn = duckdb.connect(str(db_path))
    saved_count = 0

    try:
        # Save individual records only if in "full" mode
        if storage_mode == "full":
            for record in records:
                input_tokens = record.token_usage.input_tokens if record.token_usage else 0
                output_tokens = record.token_usage.output_tokens if record.token_usage else 0
                cache_creation_tokens = record.token_usage.cache_creation_tokens if record.token_usage else 0
                cache_read_tokens = record.token_usage.cache_read_tokens if record.token_usage else 0
                total_tokens = record.token_usage.total_tokens if record.token_usage else 0

                try:
                    # Check if record exists
                    result = conn.execute("""
                        SELECT 1 FROM usage_records
                        WHERE session_id = ? AND message_uuid = ?
                    """, [record.session_id, record.message_uuid]).fetchone()

                    if not result:
                        # Get next ID from sequence
                        next_id = conn.execute("SELECT nextval('usage_records_id_seq')").fetchone()[0]

                        conn.execute("""
                            INSERT INTO usage_records (
                                id, date, timestamp, session_id, message_uuid, message_type,
                                model, folder, git_branch, version,
                                input_tokens, output_tokens,
                                cache_creation_tokens, cache_read_tokens, total_tokens,
                                device_id, device_name, device_type
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [
                            next_id,
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
                            device_id,
                            device_name,
                            device_type,
                        ])
                        saved_count += 1
                except duckdb.ConstraintException:
                    # Record already exists, skip
                    pass

        # Update daily snapshots
        if storage_mode == "full":
            timestamp = datetime.now().isoformat()

            # Get all dates that currently have usage_records
            dates_result = conn.execute("SELECT DISTINCT date FROM usage_records").fetchall()
            dates_with_records = [row[0] for row in dates_result]

            for date in dates_with_records:
                row = conn.execute("""
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
                """, [date]).fetchone()

                conn.execute("""
                    INSERT OR REPLACE INTO daily_snapshots (
                        date, total_prompts, total_responses, total_sessions, total_tokens,
                        input_tokens, output_tokens, cache_creation_tokens,
                        cache_read_tokens, snapshot_timestamp,
                        device_id, device_name, device_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
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
                ])
        else:
            # Aggregate mode
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

                if record.is_user_prompt:
                    daily_aggregates[date_key]["prompts"] += 1
                elif record.is_assistant_response:
                    daily_aggregates[date_key]["responses"] += 1

                if record.token_usage:
                    daily_aggregates[date_key]["input_tokens"] += record.token_usage.input_tokens
                    daily_aggregates[date_key]["output_tokens"] += record.token_usage.output_tokens
                    daily_aggregates[date_key]["cache_creation_tokens"] += record.token_usage.cache_creation_tokens
                    daily_aggregates[date_key]["cache_read_tokens"] += record.token_usage.cache_read_tokens
                    daily_aggregates[date_key]["total_tokens"] += record.token_usage.total_tokens

            timestamp = datetime.now().isoformat()
            for date_key, agg in daily_aggregates.items():
                existing = conn.execute("""
                    SELECT total_prompts, total_responses, total_sessions, total_tokens,
                           input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens
                    FROM daily_snapshots WHERE date = ?
                """, [date_key]).fetchone()

                if existing:
                    conn.execute("""
                        INSERT OR REPLACE INTO daily_snapshots (
                            date, total_prompts, total_responses, total_sessions, total_tokens,
                            input_tokens, output_tokens, cache_creation_tokens,
                            cache_read_tokens, snapshot_timestamp,
                            device_id, device_name, device_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
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
                    ])
                else:
                    conn.execute("""
                        INSERT INTO daily_snapshots (
                            date, total_prompts, total_responses, total_sessions, total_tokens,
                            input_tokens, output_tokens, cache_creation_tokens,
                            cache_read_tokens, snapshot_timestamp,
                            device_id, device_name, device_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
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
                    ])
                saved_count += 1

    finally:
        conn.close()

    return saved_count


def save_limits_snapshot(
    session_pct: int,
    week_pct: int,
    opus_pct: int,
    session_reset: str,
    week_reset: str,
    opus_reset: str,
    db_path: Path = DEFAULT_DB_PATH,
    device_id: Optional[str] = None,
    device_name: Optional[str] = None,
    device_type: Optional[str] = None,
) -> None:
    """
    Save usage limits snapshot to the DuckDB database.

    Args:
        session_pct: Session usage percentage
        week_pct: Week usage percentage
        opus_pct: Opus usage percentage
        session_reset: Session reset time
        week_reset: Week reset time
        opus_reset: Opus reset time
        db_path: Path to the DuckDB database file
        device_id: Device identifier
        device_name: Device name
        device_type: Device type
    """
    require_duckdb()
    init_database(db_path)

    conn = duckdb.connect(str(db_path))

    try:
        timestamp = datetime.now().isoformat()
        date = datetime.now().strftime("%Y-%m-%d")

        conn.execute("""
            INSERT OR REPLACE INTO limits_snapshots (
                timestamp, date, session_pct, week_pct, opus_pct,
                session_reset, week_reset, opus_reset,
                device_id, device_name, device_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
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
        ])

    finally:
        conn.close()


def load_historical_records(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH
) -> list[UsageRecord]:
    """
    Load historical usage records from the DuckDB database.

    Args:
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        db_path: Path to the DuckDB database file

    Returns:
        List of UsageRecord objects
    """
    require_duckdb()

    if not db_path.exists():
        return []

    conn = duckdb.connect(str(db_path))

    try:
        query = "SELECT * FROM usage_records WHERE 1=1"
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

            record = UsageRecord(
                timestamp=datetime.fromisoformat(row_dict["timestamp"]),
                session_id=row_dict["session_id"],
                message_uuid=row_dict["message_uuid"],
                message_type=row_dict["message_type"],
                model=row_dict["model"],
                folder=row_dict["folder"],
                git_branch=row_dict["git_branch"],
                version=row_dict["version"],
                token_usage=token_usage,
            )
            records.append(record)

        return records
    finally:
        conn.close()


def get_database_stats(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """
    Get statistics about the historical database.

    Args:
        db_path: Path to the DuckDB database file

    Returns:
        Dictionary with database statistics
    """
    require_duckdb()

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

    conn = duckdb.connect(str(db_path))

    try:
        # Basic counts
        total_records = conn.execute("SELECT COUNT(*) FROM usage_records").fetchone()[0]
        total_days = conn.execute("SELECT COUNT(DISTINCT date) FROM usage_records").fetchone()[0]

        date_range = conn.execute("SELECT MIN(date), MAX(date) FROM usage_records").fetchone()
        oldest_date, newest_date = date_range

        newest_timestamp = conn.execute(
            "SELECT MAX(snapshot_timestamp) FROM daily_snapshots"
        ).fetchone()[0]

        # Aggregate statistics
        agg_row = conn.execute("""
            SELECT
                SUM(total_tokens) as total_tokens,
                SUM(total_prompts) as total_prompts,
                SUM(total_responses) as total_responses,
                SUM(total_sessions) as total_sessions
            FROM daily_snapshots
        """).fetchone()

        total_tokens = agg_row[0] or 0
        total_prompts = agg_row[1] or 0
        total_responses = agg_row[2] or 0
        total_sessions = agg_row[3] or 0

        # Tokens by model
        tokens_by_model = {}
        if total_records > 0:
            model_rows = conn.execute("""
                SELECT model, SUM(total_tokens) as tokens
                FROM usage_records
                WHERE model IS NOT NULL
                GROUP BY model
                ORDER BY tokens DESC
            """).fetchall()
            tokens_by_model = {row[0]: row[1] for row in model_rows if row[0]}

        # Calculate costs
        total_cost = 0.0
        cost_by_model = {}

        if total_records > 0:
            cost_rows = conn.execute("""
                SELECT
                    ur.model,
                    SUM(ur.input_tokens) as total_input,
                    SUM(ur.output_tokens) as total_output,
                    SUM(ur.cache_creation_tokens) as total_cache_write,
                    SUM(ur.cache_read_tokens) as total_cache_read,
                    mp.input_price_per_mtok,
                    mp.output_price_per_mtok,
                    mp.cache_write_price_per_mtok,
                    mp.cache_read_price_per_mtok
                FROM usage_records ur
                LEFT JOIN model_pricing mp ON ur.model = mp.model_name
                WHERE ur.model IS NOT NULL
                GROUP BY ur.model, mp.input_price_per_mtok, mp.output_price_per_mtok,
                         mp.cache_write_price_per_mtok, mp.cache_read_price_per_mtok
            """).fetchall()

            for row in cost_rows:
                model = row[0]
                input_tokens = row[1] or 0
                output_tokens = row[2] or 0
                cache_write_tokens = row[3] or 0
                cache_read_tokens = row[4] or 0
                input_price = row[5] or 0.0
                output_price = row[6] or 0.0
                cache_write_price = row[7] or 0.0
                cache_read_price = row[8] or 0.0

                model_cost = (
                    (input_tokens / 1_000_000) * input_price +
                    (output_tokens / 1_000_000) * output_price +
                    (cache_write_tokens / 1_000_000) * cache_write_price +
                    (cache_read_tokens / 1_000_000) * cache_read_price
                )

                cost_by_model[model] = model_cost
                total_cost += model_cost

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


def get_limits_data(db_path: Path = DEFAULT_DB_PATH) -> dict[str, dict[str, int]]:
    """
    Get daily maximum limits percentages from the database.

    Returns:
        Dictionary mapping dates to max week_pct and opus_pct
    """
    require_duckdb()

    if not db_path.exists():
        return {}

    conn = duckdb.connect(str(db_path))

    try:
        rows = conn.execute("""
            SELECT
                date,
                MAX(week_pct) as max_week,
                MAX(opus_pct) as max_opus
            FROM limits_snapshots
            GROUP BY date
            ORDER BY date
        """).fetchall()

        raw_data = {}
        dates = []
        for row in rows:
            date = row[0]
            dates.append(date)
            raw_data[date] = {
                "week_pct": row[1] or 0,
                "opus_pct": row[2] or 0
            }

        if not dates:
            return {}

        # Backfill missing days
        from datetime import timedelta
        start_date = datetime.strptime(min(dates), "%Y-%m-%d")
        end_date = datetime.strptime(max(dates), "%Y-%m-%d")

        result = {}
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")

            if date_str in raw_data:
                result[date_str] = raw_data[date_str]
            else:
                # Backfill logic
                next_date = current_date + timedelta(days=1)
                found_data = None

                while next_date <= end_date:
                    next_date_str = next_date.strftime("%Y-%m-%d")
                    if next_date_str in raw_data:
                        found_data = raw_data[next_date_str]
                        break
                    next_date += timedelta(days=1)

                if found_data:
                    result[date_str] = found_data
                else:
                    prev_date = current_date - timedelta(days=1)
                    while prev_date >= start_date:
                        prev_date_str = prev_date.strftime("%Y-%m-%d")
                        if prev_date_str in result:
                            result[date_str] = result[prev_date_str]
                            break
                        prev_date -= timedelta(days=1)

                    if date_str not in result:
                        result[date_str] = {"week_pct": 0, "opus_pct": 0}

            current_date += timedelta(days=1)

        return result
    finally:
        conn.close()


def get_latest_limits(db_path: Path = DEFAULT_DB_PATH) -> dict | None:
    """
    Get the most recent limits snapshot from the database.

    Returns:
        Dictionary with latest limits, or None if no data
    """
    require_duckdb()

    if not db_path.exists():
        return None

    conn = duckdb.connect(str(db_path))

    try:
        row = conn.execute("""
            SELECT session_pct, week_pct, opus_pct,
                   session_reset, week_reset, opus_reset
            FROM limits_snapshots
            ORDER BY timestamp DESC
            LIMIT 1
        """).fetchone()

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


def get_stale_files(
    all_files: list[Path],
    db_path: Path = DEFAULT_DB_PATH
) -> tuple[list[Path], list[str]]:
    """
    Identify which JSONL files need to be re-parsed.

    Args:
        all_files: List of all JSONL file paths
        db_path: Path to the DuckDB database file

    Returns:
        Tuple of (stale_files, deleted_file_paths)
    """
    require_duckdb()

    if not db_path.exists():
        return (all_files, [])

    init_database(db_path)

    conn = duckdb.connect(str(db_path))
    stale_files = []
    deleted_files = []

    try:
        rows = conn.execute(
            "SELECT file_path, mtime_ns, size_bytes FROM file_metadata"
        ).fetchall()
        stored_metadata = {row[0]: (row[1], row[2]) for row in rows}

        current_file_paths = {str(f) for f in all_files}

        for file_path in all_files:
            path_str = str(file_path)
            try:
                stat = file_path.stat()
                current_mtime_ns = stat.st_mtime_ns
                current_size = stat.st_size

                if path_str not in stored_metadata:
                    stale_files.append(file_path)
                else:
                    stored_mtime_ns, stored_size = stored_metadata[path_str]
                    if current_mtime_ns != stored_mtime_ns or current_size != stored_size:
                        stale_files.append(file_path)
            except OSError:
                continue

        for stored_path in stored_metadata.keys():
            if stored_path not in current_file_paths:
                deleted_files.append(stored_path)

        return (stale_files, deleted_files)
    finally:
        conn.close()


def update_file_metadata(
    file_path: Path,
    record_count: int,
    db_path: Path = DEFAULT_DB_PATH
) -> None:
    """
    Update file metadata after successful parsing.
    """
    require_duckdb()
    init_database(db_path)

    conn = duckdb.connect(str(db_path))

    try:
        stat = file_path.stat()
        timestamp = datetime.now().isoformat()

        conn.execute("""
            INSERT OR REPLACE INTO file_metadata (
                file_path, mtime_ns, size_bytes, record_count, last_parsed
            ) VALUES (?, ?, ?, ?, ?)
        """, [
            str(file_path),
            stat.st_mtime_ns,
            stat.st_size,
            record_count,
            timestamp,
        ])

    finally:
        conn.close()


def remove_deleted_file_metadata(
    deleted_paths: list[str],
    db_path: Path = DEFAULT_DB_PATH
) -> None:
    """
    Remove metadata for files that no longer exist.
    """
    require_duckdb()

    if not deleted_paths or not db_path.exists():
        return

    conn = duckdb.connect(str(db_path))

    try:
        for path in deleted_paths:
            conn.execute("DELETE FROM file_metadata WHERE file_path = ?", [path])
    finally:
        conn.close()


#endregion
