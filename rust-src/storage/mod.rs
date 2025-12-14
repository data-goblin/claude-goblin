//! Storage layer for historical usage data.

mod database;

#[allow(unused_imports)]
pub use database::{
    init_database,
    save_snapshot,
    get_daily_snapshots,
    get_database_stats,
    load_historical_records,
    DatabaseStats,
    DailySnapshot,
};
