//! Configuration and settings for Claude Goblin.

mod settings;

#[allow(unused_imports)]
pub use settings::{
    get_claude_data_dir,
    get_claude_jsonl_files,
    get_db_path,
    DEFAULT_REFRESH_INTERVAL,
    ACTIVITY_GRAPH_DAYS,
    GRAPH_WEEKS,
    GRAPH_DAYS_PER_WEEK,
};
