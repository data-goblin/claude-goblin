//! Daily statistics aggregation.

use std::collections::{HashMap, HashSet};
use chrono::{Local, Duration};

use crate::models::UsageRecord;


/// Aggregated statistics for a single day.
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct DailyStats {
    pub date: String,
    pub total_prompts: i64,
    pub total_responses: i64,
    pub total_sessions: i64,
    pub total_tokens: i64,
    pub input_tokens: i64,
    pub output_tokens: i64,
    pub cache_creation_tokens: i64,
    pub cache_read_tokens: i64,
    pub models: HashSet<String>,
    pub folders: HashSet<String>,
}


impl Default for DailyStats {
    fn default() -> Self {
        Self {
            date: String::new(),
            total_prompts: 0,
            total_responses: 0,
            total_sessions: 0,
            total_tokens: 0,
            input_tokens: 0,
            output_tokens: 0,
            cache_creation_tokens: 0,
            cache_read_tokens: 0,
            models: HashSet::new(),
            folders: HashSet::new(),
        }
    }
}


/// Complete statistics across all time periods.
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct AggregatedStats {
    pub daily_stats: HashMap<String, DailyStats>,
    pub overall_totals: DailyStats,
}


/// Aggregate usage records by day.
#[allow(dead_code)]
pub fn aggregate_by_day(records: &[UsageRecord]) -> HashMap<String, DailyStats> {
    if records.is_empty() {
        return HashMap::new();
    }

    // Group records by date
    let mut daily_data: HashMap<String, Vec<&UsageRecord>> = HashMap::new();
    for record in records {
        daily_data
            .entry(record.date_key())
            .or_default()
            .push(record);
    }

    // Aggregate statistics for each day
    let mut daily_stats = HashMap::new();
    for (date, day_records) in daily_data {
        daily_stats.insert(date.clone(), calculate_day_stats(&date, &day_records));
    }

    daily_stats
}


/// Calculate overall statistics across all records.
pub fn calculate_overall_stats(records: &[UsageRecord]) -> DailyStats {
    if records.is_empty() {
        return DailyStats {
            date: "all".to_string(),
            ..Default::default()
        };
    }

    let record_refs: Vec<&UsageRecord> = records.iter().collect();
    calculate_day_stats("all", &record_refs)
}


/// Create complete aggregated statistics from usage records.
#[allow(dead_code)]
pub fn aggregate_all(records: &[UsageRecord]) -> AggregatedStats {
    AggregatedStats {
        daily_stats: aggregate_by_day(records),
        overall_totals: calculate_overall_stats(records),
    }
}


/// Get a list of dates for the specified range, ending today.
#[allow(dead_code)]
pub fn get_date_range(daily_stats: &HashMap<String, DailyStats>, days: usize) -> Vec<String> {
    if daily_stats.is_empty() {
        return Vec::new();
    }

    let today = Local::now().date_naive();
    let start_date = today - Duration::days((days - 1) as i64);

    let mut date_range = Vec::new();
    let mut current_date = start_date;

    while current_date <= today {
        date_range.push(current_date.format("%Y-%m-%d").to_string());
        current_date += Duration::days(1);
    }

    date_range
}


/// Calculate statistics for a single day's records.
fn calculate_day_stats(date: &str, records: &[&UsageRecord]) -> DailyStats {
    let mut unique_sessions = HashSet::new();
    let mut models = HashSet::new();
    let mut folders = HashSet::new();

    let mut total_prompts = 0i64;
    let mut total_responses = 0i64;
    let mut total_tokens = 0i64;
    let mut input_tokens = 0i64;
    let mut output_tokens = 0i64;
    let mut cache_creation_tokens = 0i64;
    let mut cache_read_tokens = 0i64;

    for record in records {
        unique_sessions.insert(record.session_id.clone());

        if let Some(model) = &record.model {
            models.insert(model.clone());
        }
        folders.insert(record.folder.clone());

        // Count message types
        if record.is_user_prompt() {
            total_prompts += 1;
        } else if record.is_assistant_response() {
            total_responses += 1;
        }

        // Token usage only available on assistant responses
        if let Some(usage) = &record.token_usage {
            total_tokens += usage.total_tokens();
            input_tokens += usage.input_tokens;
            output_tokens += usage.output_tokens;
            cache_creation_tokens += usage.cache_creation_tokens;
            cache_read_tokens += usage.cache_read_tokens;
        }
    }

    DailyStats {
        date: date.to_string(),
        total_prompts,
        total_responses,
        total_sessions: unique_sessions.len() as i64,
        total_tokens,
        input_tokens,
        output_tokens,
        cache_creation_tokens,
        cache_read_tokens,
        models,
        folders,
    }
}


#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use crate::models::TokenUsage;
    use std::sync::atomic::{AtomicU32, Ordering};

    static COUNTER: AtomicU32 = AtomicU32::new(0);

    fn create_test_record(message_type: &str, model: Option<&str>) -> UsageRecord {
        let id = COUNTER.fetch_add(1, Ordering::SeqCst);
        UsageRecord {
            timestamp: Utc::now(),
            session_id: "test-session".to_string(),
            message_uuid: format!("uuid-{}", id),
            message_type: message_type.to_string(),
            model: model.map(String::from),
            folder: "/test".to_string(),
            git_branch: None,
            version: "1.0.0".to_string(),
            token_usage: if message_type == "assistant" {
                Some(TokenUsage {
                    input_tokens: 100,
                    output_tokens: 200,
                    cache_creation_tokens: 50,
                    cache_read_tokens: 25,
                })
            } else {
                None
            },
            content: None,
            char_count: 0,
        }
    }

    #[test]
    fn test_aggregate_empty() {
        let records: Vec<UsageRecord> = vec![];
        let result = aggregate_by_day(&records);
        assert!(result.is_empty());
    }

    #[test]
    fn test_calculate_overall_stats() {
        let records = vec![
            create_test_record("user", None),
            create_test_record("assistant", Some("claude-sonnet")),
        ];
        let stats = calculate_overall_stats(&records);

        assert_eq!(stats.total_prompts, 1);
        assert_eq!(stats.total_responses, 1);
        assert_eq!(stats.total_tokens, 375); // 100 + 200 + 50 + 25
    }
}
