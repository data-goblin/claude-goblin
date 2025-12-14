//! Usage record models for Claude Code events.

use chrono::{DateTime, Local, Utc};
use serde::{Deserialize, Serialize};


/// Token usage for a single API call.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, Default)]
pub struct TokenUsage {
    pub input_tokens: i64,
    pub output_tokens: i64,
    pub cache_creation_tokens: i64,
    pub cache_read_tokens: i64,
}


impl TokenUsage {
    /// Calculate total tokens across all categories.
    pub fn total_tokens(&self) -> i64 {
        self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
    }
}


/// A single usage event from Claude Code.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageRecord {
    pub timestamp: DateTime<Utc>,
    pub session_id: String,
    pub message_uuid: String,
    pub message_type: String,
    pub model: Option<String>,
    pub folder: String,
    pub git_branch: Option<String>,
    pub version: String,
    pub token_usage: Option<TokenUsage>,
    #[serde(default)]
    pub content: Option<String>,
    #[serde(default)]
    pub char_count: i64,
}


impl UsageRecord {
    /// Get date string in YYYY-MM-DD format for grouping.
    ///
    /// Converts UTC timestamp to local timezone before extracting date.
    pub fn date_key(&self) -> String {
        let local: DateTime<Local> = self.timestamp.into();
        local.format("%Y-%m-%d").to_string()
    }

    /// Check if this is a user prompt message.
    pub fn is_user_prompt(&self) -> bool {
        self.message_type == "user"
    }

    /// Check if this is an assistant response message.
    pub fn is_assistant_response(&self) -> bool {
        self.message_type == "assistant"
    }

    /// Get total tokens for this record (0 if no token usage).
    pub fn total_tokens(&self) -> i64 {
        self.token_usage.map(|t| t.total_tokens()).unwrap_or(0)
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_token_usage_total() {
        let usage = TokenUsage {
            input_tokens: 100,
            output_tokens: 200,
            cache_creation_tokens: 50,
            cache_read_tokens: 25,
        };
        assert_eq!(usage.total_tokens(), 375);
    }

    #[test]
    fn test_message_type_checks() {
        let record = UsageRecord {
            timestamp: Utc::now(),
            session_id: "test".to_string(),
            message_uuid: "uuid".to_string(),
            message_type: "user".to_string(),
            model: None,
            folder: "/test".to_string(),
            git_branch: None,
            version: "1.0".to_string(),
            token_usage: None,
            content: None,
            char_count: 0,
        };
        assert!(record.is_user_prompt());
        assert!(!record.is_assistant_response());
    }
}
