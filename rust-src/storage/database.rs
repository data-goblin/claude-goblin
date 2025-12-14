//! SQLite database operations for historical usage data.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use chrono::{Local, Utc};
use rusqlite::{Connection, params};

use crate::models::UsageRecord;


/// Get the default database path.
pub fn default_db_path() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".claude")
        .join("usage")
        .join("usage_history.db")
}


/// Daily snapshot of aggregated usage.
#[derive(Debug, Clone)]
pub struct DailySnapshot {
    pub date: String,
    pub total_prompts: i64,
    pub total_responses: i64,
    pub total_sessions: i64,
    pub total_tokens: i64,
    pub input_tokens: i64,
    pub output_tokens: i64,
    pub cache_creation_tokens: i64,
    pub cache_read_tokens: i64,
}


/// Database statistics.
#[derive(Debug, Clone, Default)]
pub struct DatabaseStats {
    pub total_records: i64,
    pub total_days: i64,
    pub oldest_date: Option<String>,
    pub newest_date: Option<String>,
    pub total_tokens: i64,
    pub total_prompts: i64,
    pub total_responses: i64,
    pub total_sessions: i64,
    pub tokens_by_model: HashMap<String, i64>,
    pub cost_by_model: HashMap<String, f64>,
    pub total_cost: f64,
}


/// Initialize the database with required tables.
pub fn init_database(db_path: &Path) -> Result<()> {
    // Create parent directory if needed
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("Failed to create directory: {}", parent.display()))?;
    }

    let conn = Connection::open(db_path)
        .with_context(|| format!("Failed to open database: {}", db_path.display()))?;

    // Table for daily aggregated snapshots
    conn.execute(
        "CREATE TABLE IF NOT EXISTS daily_snapshots (
            date TEXT PRIMARY KEY,
            total_prompts INTEGER NOT NULL,
            total_responses INTEGER NOT NULL,
            total_sessions INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cache_creation_tokens INTEGER NOT NULL,
            cache_read_tokens INTEGER NOT NULL,
            snapshot_timestamp TEXT NOT NULL
        )",
        [],
    )?;

    // Table for detailed usage records
    conn.execute(
        "CREATE TABLE IF NOT EXISTS usage_records (
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
            UNIQUE(session_id, message_uuid)
        )",
        [],
    )?;

    // Index for faster date-based queries
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_records_date ON usage_records(date)",
        [],
    )?;

    // Table for model pricing
    conn.execute(
        "CREATE TABLE IF NOT EXISTS model_pricing (
            model_name TEXT PRIMARY KEY,
            input_price_per_mtok REAL NOT NULL,
            output_price_per_mtok REAL NOT NULL,
            cache_write_price_per_mtok REAL NOT NULL,
            cache_read_price_per_mtok REAL NOT NULL,
            last_updated TEXT NOT NULL,
            notes TEXT
        )",
        [],
    )?;

    // Populate pricing data
    let timestamp = Utc::now().to_rfc3339();
    let pricing_data = [
        ("claude-opus-4-1-20250805", 15.00, 75.00, 18.75, 1.50, "Current flagship model"),
        ("claude-sonnet-4-5-20250929", 3.00, 15.00, 3.75, 0.30, "Current balanced model"),
        ("claude-haiku-4-5-20251001", 1.00, 5.00, 1.25, 0.10, "Claude Haiku 4.5"),
        ("claude-haiku-3-5-20241022", 0.80, 4.00, 1.00, 0.08, "Claude 3.5 Haiku"),
        ("claude-sonnet-4-20250514", 3.00, 15.00, 3.75, 0.30, "Legacy Sonnet 4"),
        ("claude-opus-4-20250514", 15.00, 75.00, 18.75, 1.50, "Legacy Opus 4"),
        ("<synthetic>", 0.00, 0.00, 0.00, 0.00, "Test/synthetic model"),
    ];

    for (model, input, output, cache_write, cache_read, notes) in pricing_data {
        conn.execute(
            "INSERT OR REPLACE INTO model_pricing (
                model_name, input_price_per_mtok, output_price_per_mtok,
                cache_write_price_per_mtok, cache_read_price_per_mtok,
                last_updated, notes
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![model, input, output, cache_write, cache_read, timestamp, notes],
        )?;
    }

    Ok(())
}


/// Save usage records to the database.
///
/// Returns the number of new records saved.
pub fn save_snapshot(records: &[UsageRecord], db_path: &Path) -> Result<usize> {
    if records.is_empty() {
        return Ok(0);
    }

    init_database(db_path)?;

    let conn = Connection::open(db_path)?;
    let mut saved_count = 0;

    // Save individual records
    for record in records {
        let (input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, total_tokens) =
            if let Some(usage) = &record.token_usage {
                (
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.cache_creation_tokens,
                    usage.cache_read_tokens,
                    usage.total_tokens(),
                )
            } else {
                (0, 0, 0, 0, 0)
            };

        let result = conn.execute(
            "INSERT INTO usage_records (
                date, timestamp, session_id, message_uuid, message_type,
                model, folder, git_branch, version,
                input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, total_tokens
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14)",
            params![
                record.date_key(),
                record.timestamp.to_rfc3339(),
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
            ],
        );

        match result {
            Ok(_) => saved_count += 1,
            Err(rusqlite::Error::SqliteFailure(err, _))
                if err.code == rusqlite::ErrorCode::ConstraintViolation =>
            {
                // Record already exists, skip
            }
            Err(e) => return Err(e.into()),
        }
    }

    // Update daily snapshots for dates with records
    let timestamp = Local::now().to_rfc3339();

    let mut stmt = conn.prepare("SELECT DISTINCT date FROM usage_records")?;
    let dates: Vec<String> = stmt
        .query_map([], |row| row.get(0))?
        .filter_map(|r| r.ok())
        .collect();

    for date in dates {
        let row: (i64, i64, i64, i64, i64, i64, i64, i64) = conn.query_row(
            "SELECT
                SUM(CASE WHEN message_type = 'user' THEN 1 ELSE 0 END),
                SUM(CASE WHEN message_type = 'assistant' THEN 1 ELSE 0 END),
                COUNT(DISTINCT session_id),
                SUM(total_tokens),
                SUM(input_tokens),
                SUM(output_tokens),
                SUM(cache_creation_tokens),
                SUM(cache_read_tokens)
            FROM usage_records WHERE date = ?1",
            params![date],
            |row| {
                Ok((
                    row.get(0)?,
                    row.get(1)?,
                    row.get(2)?,
                    row.get(3)?,
                    row.get(4)?,
                    row.get(5)?,
                    row.get(6)?,
                    row.get(7)?,
                ))
            },
        )?;

        conn.execute(
            "INSERT OR REPLACE INTO daily_snapshots (
                date, total_prompts, total_responses, total_sessions, total_tokens,
                input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
                snapshot_timestamp
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
            params![date, row.0, row.1, row.2, row.3, row.4, row.5, row.6, row.7, timestamp],
        )?;
    }

    Ok(saved_count)
}


/// Get daily snapshots for a date range.
pub fn get_daily_snapshots(
    db_path: &Path,
    start_date: Option<&str>,
    end_date: Option<&str>,
) -> Result<Vec<DailySnapshot>> {
    if !db_path.exists() {
        return Ok(Vec::new());
    }

    let conn = Connection::open(db_path)?;

    let mut query = "SELECT date, total_prompts, total_responses, total_sessions, total_tokens,
                     input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens
                     FROM daily_snapshots WHERE 1=1".to_string();
    let mut params_vec: Vec<Box<dyn rusqlite::ToSql>> = Vec::new();

    if let Some(start) = start_date {
        query.push_str(" AND date >= ?");
        params_vec.push(Box::new(start.to_string()));
    }
    if let Some(end) = end_date {
        query.push_str(" AND date <= ?");
        params_vec.push(Box::new(end.to_string()));
    }
    query.push_str(" ORDER BY date");

    let params_refs: Vec<&dyn rusqlite::ToSql> = params_vec.iter().map(|p| p.as_ref()).collect();
    let mut stmt = conn.prepare(&query)?;

    let snapshots = stmt
        .query_map(params_refs.as_slice(), |row| {
            Ok(DailySnapshot {
                date: row.get(0)?,
                total_prompts: row.get(1)?,
                total_responses: row.get(2)?,
                total_sessions: row.get(3)?,
                total_tokens: row.get(4)?,
                input_tokens: row.get(5)?,
                output_tokens: row.get(6)?,
                cache_creation_tokens: row.get(7)?,
                cache_read_tokens: row.get(8)?,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();

    Ok(snapshots)
}


/// Get database statistics.
pub fn get_database_stats(db_path: &Path) -> Result<DatabaseStats> {
    if !db_path.exists() {
        return Ok(DatabaseStats::default());
    }

    let conn = Connection::open(db_path)?;

    // Basic counts
    let total_records: i64 = conn.query_row(
        "SELECT COUNT(*) FROM usage_records",
        [],
        |row| row.get(0),
    ).unwrap_or(0);

    let total_days: i64 = conn.query_row(
        "SELECT COUNT(DISTINCT date) FROM usage_records",
        [],
        |row| row.get(0),
    ).unwrap_or(0);

    let (oldest_date, newest_date): (Option<String>, Option<String>) = conn
        .query_row(
            "SELECT MIN(date), MAX(date) FROM usage_records",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap_or((None, None));

    // Aggregates from daily_snapshots
    let (total_tokens, total_prompts, total_responses, total_sessions): (i64, i64, i64, i64) = conn
        .query_row(
            "SELECT COALESCE(SUM(total_tokens), 0), COALESCE(SUM(total_prompts), 0),
                    COALESCE(SUM(total_responses), 0), COALESCE(SUM(total_sessions), 0)
             FROM daily_snapshots",
            [],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
        )
        .unwrap_or((0, 0, 0, 0));

    // Tokens by model
    let mut tokens_by_model = HashMap::new();
    if total_records > 0 {
        let mut stmt = conn.prepare(
            "SELECT model, SUM(total_tokens) FROM usage_records
             WHERE model IS NOT NULL GROUP BY model ORDER BY SUM(total_tokens) DESC",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?))
        })?;
        for row in rows.flatten() {
            tokens_by_model.insert(row.0, row.1);
        }
    }

    // Cost calculation
    let mut cost_by_model = HashMap::new();
    let mut total_cost = 0.0;

    if total_records > 0 {
        let mut stmt = conn.prepare(
            "SELECT ur.model,
                    SUM(ur.input_tokens), SUM(ur.output_tokens),
                    SUM(ur.cache_creation_tokens), SUM(ur.cache_read_tokens),
                    mp.input_price_per_mtok, mp.output_price_per_mtok,
                    mp.cache_write_price_per_mtok, mp.cache_read_price_per_mtok
             FROM usage_records ur
             LEFT JOIN model_pricing mp ON ur.model = mp.model_name
             WHERE ur.model IS NOT NULL
             GROUP BY ur.model",
        )?;

        let rows = stmt.query_map([], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, i64>(1).unwrap_or(0),
                row.get::<_, i64>(2).unwrap_or(0),
                row.get::<_, i64>(3).unwrap_or(0),
                row.get::<_, i64>(4).unwrap_or(0),
                row.get::<_, f64>(5).unwrap_or(0.0),
                row.get::<_, f64>(6).unwrap_or(0.0),
                row.get::<_, f64>(7).unwrap_or(0.0),
                row.get::<_, f64>(8).unwrap_or(0.0),
            ))
        })?;

        for row in rows.flatten() {
            let (model, input, output, cache_write, cache_read, ip, op, cwp, crp) = row;
            let cost = (input as f64 / 1_000_000.0) * ip
                + (output as f64 / 1_000_000.0) * op
                + (cache_write as f64 / 1_000_000.0) * cwp
                + (cache_read as f64 / 1_000_000.0) * crp;
            cost_by_model.insert(model, cost);
            total_cost += cost;
        }
    }

    Ok(DatabaseStats {
        total_records,
        total_days,
        oldest_date,
        newest_date,
        total_tokens,
        total_prompts,
        total_responses,
        total_sessions,
        tokens_by_model,
        cost_by_model,
        total_cost,
    })
}


#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;
    use crate::models::TokenUsage;

    fn create_test_record() -> UsageRecord {
        UsageRecord {
            timestamp: Utc::now(),
            session_id: "test-session".to_string(),
            message_uuid: "test-uuid".to_string(),
            message_type: "assistant".to_string(),
            model: Some("claude-sonnet-4-20250514".to_string()),
            folder: "/test".to_string(),
            git_branch: None,
            version: "1.0.0".to_string(),
            token_usage: Some(TokenUsage {
                input_tokens: 100,
                output_tokens: 200,
                cache_creation_tokens: 50,
                cache_read_tokens: 25,
            }),
            content: None,
            char_count: 0,
        }
    }

    #[test]
    fn test_init_database() {
        let tmp_dir = TempDir::new().unwrap();
        let db_path = tmp_dir.path().join("test.db");

        init_database(&db_path).unwrap();
        assert!(db_path.exists());
    }

    #[test]
    fn test_save_and_retrieve() {
        let tmp_dir = TempDir::new().unwrap();
        let db_path = tmp_dir.path().join("test.db");

        let record = create_test_record();
        let saved = save_snapshot(&[record], &db_path).unwrap();
        assert_eq!(saved, 1);

        let stats = get_database_stats(&db_path).unwrap();
        assert_eq!(stats.total_records, 1);
    }

    #[test]
    fn test_duplicate_prevention() {
        let tmp_dir = TempDir::new().unwrap();
        let db_path = tmp_dir.path().join("test.db");

        let record = create_test_record();
        save_snapshot(&[record.clone()], &db_path).unwrap();
        let saved = save_snapshot(&[record], &db_path).unwrap();

        // Second save should not add duplicates
        assert_eq!(saved, 0);
    }
}
