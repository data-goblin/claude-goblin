//! Storage layer for historical usage data.

mod database;

pub use database::{
    init_database,
    save_snapshot,
    get_daily_snapshots,
    get_database_stats,
    DatabaseStats,
    DailySnapshot,
};
