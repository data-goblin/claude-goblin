//! JSONL parser for Claude Code session logs.

use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use serde_json::Value;

use crate::models::{TokenUsage, UsageRecord};


/// Parse a single JSONL file and return UsageRecord objects.
pub fn parse_jsonl_file(file_path: &Path) -> Result<Vec<UsageRecord>> {
    let file = File::open(file_path)
        .with_context(|| format!("Failed to open file: {}", file_path.display()))?;

    let reader = BufReader::new(file);
    let mut records = Vec::new();

    for (line_num, line_result) in reader.lines().enumerate() {
        let line = match line_result {
            Ok(l) => l,
            Err(e) => {
                eprintln!(
                    "Warning: Error reading line {} in {}: {}",
                    line_num + 1,
                    file_path.display(),
                    e
                );
                continue;
            }
        };

        let line = line.trim();
        if line.is_empty() {
            continue;
        }

        match serde_json::from_str::<Value>(line) {
            Ok(data) => {
                if let Some(record) = parse_record(&data) {
                    records.push(record);
                }
            }
            Err(e) => {
                eprintln!(
                    "Warning: Skipping malformed JSON at {}:{}: {}",
                    file_path.display(),
                    line_num + 1,
                    e
                );
            }
        }
    }

    Ok(records)
}


/// Parse multiple JSONL files and return all usage records.
pub fn parse_all_jsonl_files(file_paths: &[&Path]) -> Result<Vec<UsageRecord>> {
    if file_paths.is_empty() {
        anyhow::bail!("No JSONL files provided to parse");
    }

    let mut all_records = Vec::new();

    for file_path in file_paths {
        match parse_jsonl_file(file_path) {
            Ok(records) => all_records.extend(records),
            Err(e) => {
                eprintln!("Warning: Error parsing {}: {}", file_path.display(), e);
            }
        }
    }

    Ok(all_records)
}


/// Parse a single JSON record into a UsageRecord.
fn parse_record(data: &Value) -> Option<UsageRecord> {
    let message_type = data.get("type")?.as_str()?;

    // Only process user and assistant messages
    if message_type != "user" && message_type != "assistant" {
        return None;
    }

    // Parse timestamp
    let timestamp_str = data.get("timestamp")?.as_str()?;
    let timestamp = parse_timestamp(timestamp_str)?;

    // Extract metadata
    let session_id = data
        .get("sessionId")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown")
        .to_string();

    let message_uuid = data
        .get("uuid")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown")
        .to_string();

    let folder = data
        .get("cwd")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown")
        .to_string();

    let git_branch = data
        .get("gitBranch")
        .and_then(|v| v.as_str())
        .map(String::from);

    let version = data
        .get("version")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown")
        .to_string();

    // Extract message data
    let message = data.get("message")?;
    let model = message.get("model").and_then(|v| v.as_str()).map(String::from);

    // Filter out synthetic models
    if model.as_deref() == Some("<synthetic>") {
        return None;
    }

    // Extract content for analysis
    let (content, char_count) = extract_content(message);

    // Extract token usage (only for assistant messages)
    let token_usage = if message_type == "assistant" {
        extract_token_usage(message)
    } else {
        None
    };

    Some(UsageRecord {
        timestamp,
        session_id,
        message_uuid,
        message_type: message_type.to_string(),
        model,
        folder,
        git_branch,
        version,
        token_usage,
        content,
        char_count,
    })
}


/// Parse ISO 8601 timestamp string to DateTime<Utc>.
fn parse_timestamp(s: &str) -> Option<DateTime<Utc>> {
    // Handle "Z" suffix
    let normalized = s.replace("Z", "+00:00");
    DateTime::parse_from_rfc3339(&normalized)
        .ok()
        .map(|dt| dt.with_timezone(&Utc))
}


/// Extract content and character count from message.
fn extract_content(message: &Value) -> (Option<String>, i64) {
    let content_val = message.get("content");

    match content_val {
        Some(Value::String(s)) => {
            let char_count = s.len() as i64;
            (Some(s.clone()), char_count)
        }
        Some(Value::Array(blocks)) => {
            let mut text_parts = Vec::new();
            for block in blocks {
                if let Some(block_obj) = block.as_object() {
                    if block_obj.get("type").and_then(|t| t.as_str()) == Some("text") {
                        if let Some(text) = block_obj.get("text").and_then(|t| t.as_str()) {
                            text_parts.push(text.to_string());
                        }
                    }
                }
            }
            if text_parts.is_empty() {
                (None, 0)
            } else {
                let content = text_parts.join("\n");
                let char_count = content.len() as i64;
                (Some(content), char_count)
            }
        }
        _ => (None, 0),
    }
}


/// Extract token usage from assistant message.
fn extract_token_usage(message: &Value) -> Option<TokenUsage> {
    let usage = message.get("usage")?;

    let input_tokens = usage
        .get("input_tokens")
        .and_then(|v| v.as_i64())
        .unwrap_or(0);

    let output_tokens = usage
        .get("output_tokens")
        .and_then(|v| v.as_i64())
        .unwrap_or(0);

    // Cache creation tokens (sum of all cache creation fields)
    let cache_creation = usage.get("cache_creation");
    let cache_creation_tokens = if let Some(cc) = cache_creation {
        let base = cc
            .get("cache_creation_input_tokens")
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        let ephemeral_5m = cc
            .get("ephemeral_5m_input_tokens")
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        let ephemeral_1h = cc
            .get("ephemeral_1h_input_tokens")
            .and_then(|v| v.as_i64())
            .unwrap_or(0);
        base + ephemeral_5m + ephemeral_1h
    } else {
        0
    };

    let cache_read_tokens = usage
        .get("cache_read_input_tokens")
        .and_then(|v| v.as_i64())
        .unwrap_or(0);

    Some(TokenUsage {
        input_tokens,
        output_tokens,
        cache_creation_tokens,
        cache_read_tokens,
    })
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_timestamp() {
        let ts = parse_timestamp("2024-01-15T10:30:00Z").unwrap();
        assert_eq!(ts.to_rfc3339(), "2024-01-15T10:30:00+00:00");
    }

    #[test]
    fn test_parse_record_user() {
        let json = r#"{
            "type": "user",
            "timestamp": "2024-01-15T10:30:00Z",
            "sessionId": "sess-123",
            "uuid": "msg-456",
            "cwd": "/home/user/project",
            "version": "1.0.0",
            "message": {
                "content": "Hello world"
            }
        }"#;

        let data: Value = serde_json::from_str(json).unwrap();
        let record = parse_record(&data).unwrap();

        assert_eq!(record.message_type, "user");
        assert_eq!(record.session_id, "sess-123");
        assert_eq!(record.content, Some("Hello world".to_string()));
        assert!(record.token_usage.is_none());
    }

    #[test]
    fn test_parse_record_assistant_with_usage() {
        let json = r#"{
            "type": "assistant",
            "timestamp": "2024-01-15T10:30:00Z",
            "sessionId": "sess-123",
            "uuid": "msg-789",
            "cwd": "/home/user/project",
            "version": "1.0.0",
            "message": {
                "model": "claude-sonnet-4-20250514",
                "content": "Here's the answer",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_input_tokens": 25
                }
            }
        }"#;

        let data: Value = serde_json::from_str(json).unwrap();
        let record = parse_record(&data).unwrap();

        assert_eq!(record.message_type, "assistant");
        assert_eq!(record.model, Some("claude-sonnet-4-20250514".to_string()));

        let usage = record.token_usage.unwrap();
        assert_eq!(usage.input_tokens, 100);
        assert_eq!(usage.output_tokens, 50);
        assert_eq!(usage.cache_read_tokens, 25);
    }

    #[test]
    fn test_skip_synthetic_model() {
        let json = r#"{
            "type": "assistant",
            "timestamp": "2024-01-15T10:30:00Z",
            "sessionId": "sess-123",
            "uuid": "msg-789",
            "cwd": "/home/user/project",
            "version": "1.0.0",
            "message": {
                "model": "<synthetic>",
                "content": "test"
            }
        }"#;

        let data: Value = serde_json::from_str(json).unwrap();
        assert!(parse_record(&data).is_none());
    }

    #[test]
    fn test_content_blocks() {
        let json = r#"{
            "type": "user",
            "timestamp": "2024-01-15T10:30:00Z",
            "sessionId": "sess-123",
            "uuid": "msg-456",
            "cwd": "/project",
            "version": "1.0.0",
            "message": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": "World"}
                ]
            }
        }"#;

        let data: Value = serde_json::from_str(json).unwrap();
        let record = parse_record(&data).unwrap();

        assert_eq!(record.content, Some("Hello\nWorld".to_string()));
        assert_eq!(record.char_count, 11);
    }
}
