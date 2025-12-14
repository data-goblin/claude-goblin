//! Aggregation layer for usage statistics.

mod daily_stats;

#[allow(unused_imports)]
pub use daily_stats::{
    DailyStats,
    AggregatedStats,
    aggregate_by_day,
    calculate_overall_stats,
    aggregate_all,
    get_date_range,
};
