//! Visualization layer for dashboards and charts.

mod dashboard;
mod export;

pub use dashboard::{render_dashboard, anonymize_projects};
pub use export::{export_heatmap_svg, export_heatmap_png, open_file, DayStats};
