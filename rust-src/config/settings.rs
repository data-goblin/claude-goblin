//! Application settings and path constants.

use std::path::PathBuf;

use anyhow::{Context, Result};


/// Default refresh interval for dashboard (seconds).
pub const DEFAULT_REFRESH_INTERVAL: u64 = 5;

/// Number of days to show in activity graph.
pub const ACTIVITY_GRAPH_DAYS: usize = 365;

/// Graph dimensions.
pub const GRAPH_WEEKS: usize = 52;
pub const GRAPH_DAYS_PER_WEEK: usize = 7;


/// Get Claude's data directory.
pub fn get_claude_data_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".claude")
        .join("projects")
}


/// Get the database path.
pub fn get_db_path() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".claude")
        .join("usage")
        .join("usage_history.db")
}


/// Get all JSONL files from Claude's project data directory.
pub fn get_claude_jsonl_files() -> Result<Vec<PathBuf>> {
    let data_dir = get_claude_data_dir();

    if !data_dir.exists() {
        anyhow::bail!(
            "Claude data directory not found at {}. \
             Make sure Claude Code has been run at least once.",
            data_dir.display()
        );
    }

    let mut files = Vec::new();
    collect_jsonl_files(&data_dir, &mut files)?;

    Ok(files)
}


/// Recursively collect JSONL files from a directory.
fn collect_jsonl_files(dir: &PathBuf, files: &mut Vec<PathBuf>) -> Result<()> {
    if !dir.is_dir() {
        return Ok(());
    }

    let entries = std::fs::read_dir(dir)
        .with_context(|| format!("Failed to read directory: {}", dir.display()))?;

    for entry in entries.flatten() {
        let path = entry.path();

        if path.is_dir() {
            collect_jsonl_files(&path, files)?;
        } else if path.extension().map_or(false, |ext| ext == "jsonl") {
            files.push(path);
        }
    }

    Ok(())
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_constants() {
        assert_eq!(DEFAULT_REFRESH_INTERVAL, 5);
        assert_eq!(ACTIVITY_GRAPH_DAYS, 365);
        assert_eq!(GRAPH_WEEKS, 52);
        assert_eq!(GRAPH_DAYS_PER_WEEK, 7);
    }

    #[test]
    fn test_get_claude_data_dir() {
        let dir = get_claude_data_dir();
        assert!(dir.to_string_lossy().contains(".claude"));
        assert!(dir.to_string_lossy().contains("projects"));
    }

    #[test]
    fn test_get_db_path() {
        let path = get_db_path();
        assert!(path.to_string_lossy().contains(".claude"));
        assert!(path.to_string_lossy().contains("usage_history.db"));
    }
}
