//! Dashboard rendering using terminal output.

use std::collections::HashMap;

use crate::aggregation::DailyStats;
use crate::models::UsageRecord;


// Constants
const ORANGE: &str = "\x1b[38;5;208m";
const CYAN: &str = "\x1b[36m";
const DIM: &str = "\x1b[2m";
const BOLD: &str = "\x1b[1m";
const RESET: &str = "\x1b[0m";
const BAR_WIDTH: usize = 20;


/// Format number with thousands separator and appropriate suffix.
fn format_number(num: i64) -> String {
    if num >= 1_000_000_000 {
        format!("{:.1}bn", num as f64 / 1_000_000_000.0)
    } else if num >= 1_000_000 {
        format!("{:.1}M", num as f64 / 1_000_000.0)
    } else if num >= 1_000 {
        format!("{:.1}K", num as f64 / 1_000.0)
    } else {
        format!("{}", num)
    }
}


/// Create a simple text bar for visualization.
fn create_bar(value: i64, max_value: i64, width: usize, color: &str) -> String {
    if max_value == 0 {
        return "░".repeat(width);
    }

    let filled = ((value as f64 / max_value as f64) * width as f64) as usize;
    let filled = filled.min(width);

    format!(
        "{}{}{}{}{}",
        color,
        "█".repeat(filled),
        RESET,
        DIM,
        "░".repeat(width - filled),
    ) + RESET
}


/// Render the complete dashboard.
pub fn render_dashboard(
    stats: &DailyStats,
    records: &[UsageRecord],
    date_range: Option<&str>,
    fast_mode: bool,
    clear_screen: bool,
) {
    if clear_screen {
        print!("\x1b[2J\x1b[H"); // Clear screen and move cursor to top
    }

    // Render KPI section
    render_kpi_section(stats);
    println!();

    // Render model breakdown
    render_model_breakdown(records);
    println!();

    // Render project breakdown
    render_project_breakdown(records);
    println!();

    // Render footer
    render_footer(date_range, fast_mode);
}


/// Render the KPI cards section.
fn render_kpi_section(stats: &DailyStats) {
    // Create a simple 3-column layout
    let width = 28;
    let border = "─".repeat(width - 2);

    // Top borders
    println!(
        "┌{}┐  ┌{}┐  ┌{}┐",
        border, border, border
    );

    // Titles
    println!(
        "│{:^26}│  │{:^26}│  │{:^26}│",
        "Total Tokens", "Prompts Sent", "Active Sessions"
    );

    // Values
    println!(
        "│{}{}{:^26}{}│  │{}{:^26}{}│  │{}{:^26}{}│",
        BOLD, ORANGE,
        format_number(stats.total_tokens),
        RESET,
        BOLD,
        format_number(stats.total_prompts),
        RESET,
        BOLD,
        format_number(stats.total_sessions),
        RESET,
    );

    // Bottom borders
    println!(
        "└{}┘  └{}┘  └{}┘",
        border, border, border
    );
}


/// Render the model breakdown section.
fn render_model_breakdown(records: &[UsageRecord]) {
    // Aggregate tokens by model
    let mut model_tokens: HashMap<String, i64> = HashMap::new();

    for record in records {
        if let (Some(model), Some(usage)) = (&record.model, &record.token_usage) {
            if model != "<synthetic>" {
                *model_tokens.entry(model.clone()).or_insert(0) += usage.total_tokens();
            }
        }
    }

    if model_tokens.is_empty() {
        println!("{}No model data available{}", DIM, RESET);
        return;
    }

    // Calculate totals
    let total_tokens: i64 = model_tokens.values().sum();
    let max_tokens = *model_tokens.values().max().unwrap_or(&0);

    // Sort by usage
    let mut sorted_models: Vec<_> = model_tokens.into_iter().collect();
    sorted_models.sort_by(|a, b| b.1.cmp(&a.1));

    // Print header
    println!("┌────────────────────────────────────────────────────────────────────────────┐");
    println!("│ {}{}Tokens by Model{}                                                          │", BOLD, "", RESET);
    println!("├────────────────────────────────────────────────────────────────────────────┤");

    for (model, tokens) in sorted_models {
        // Shorten model name
        let mut display_name = model.clone();
        if display_name.contains('/') {
            display_name = display_name.split('/').last().unwrap_or(&display_name).to_string();
        }
        if display_name.to_lowercase().contains("claude") {
            display_name = display_name.replace("claude-", "");
        }

        let percentage = if total_tokens > 0 {
            (tokens as f64 / total_tokens as f64) * 100.0
        } else {
            0.0
        };

        let bar = create_bar(tokens, max_tokens, BAR_WIDTH, ORANGE);

        println!(
            "│ {:25} {} {}{:>10}{} {}{:>5.1}%{} │",
            &display_name[..display_name.len().min(25)],
            bar,
            ORANGE,
            format_number(tokens),
            RESET,
            CYAN,
            percentage,
            RESET,
        );
    }

    println!("└────────────────────────────────────────────────────────────────────────────┘");
}


/// Render the project breakdown section.
fn render_project_breakdown(records: &[UsageRecord]) {
    // Aggregate tokens by folder
    let mut folder_tokens: HashMap<String, i64> = HashMap::new();

    for record in records {
        if let Some(usage) = &record.token_usage {
            *folder_tokens.entry(record.folder.clone()).or_insert(0) += usage.total_tokens();
        }
    }

    if folder_tokens.is_empty() {
        println!("{}No project data available{}", DIM, RESET);
        return;
    }

    // Calculate totals
    let total_tokens: i64 = folder_tokens.values().sum();

    // Sort by usage and limit to top 10
    let mut sorted_folders: Vec<_> = folder_tokens.into_iter().collect();
    sorted_folders.sort_by(|a, b| b.1.cmp(&a.1));
    sorted_folders.truncate(10);

    let max_tokens = sorted_folders.first().map(|(_, t)| *t).unwrap_or(0);

    // Print header
    println!("┌────────────────────────────────────────────────────────────────────────────┐");
    println!("│ {}Tokens by Project{}                                                         │", BOLD, RESET);
    println!("├────────────────────────────────────────────────────────────────────────────┤");

    for (folder, tokens) in sorted_folders {
        // Shorten path
        let parts: Vec<&str> = folder.split('/').collect();
        let display_name = if parts.len() > 3 {
            format!(".../{}", parts[parts.len()-2..].join("/"))
        } else if parts.len() > 2 {
            parts[parts.len()-2..].join("/")
        } else {
            folder.clone()
        };

        let display_name = if display_name.len() > 35 {
            display_name[..35].to_string()
        } else {
            display_name
        };

        let percentage = if total_tokens > 0 {
            (tokens as f64 / total_tokens as f64) * 100.0
        } else {
            0.0
        };

        let bar = create_bar(tokens, max_tokens, BAR_WIDTH, ORANGE);

        println!(
            "│ {:35} {} {}{:>10}{} {}{:>5.1}%{} │",
            display_name,
            bar,
            ORANGE,
            format_number(tokens),
            RESET,
            CYAN,
            percentage,
            RESET,
        );
    }

    println!("└────────────────────────────────────────────────────────────────────────────┘");
}


/// Render the footer with tips and date range.
fn render_footer(date_range: Option<&str>, fast_mode: bool) {
    if fast_mode {
        println!(
            "{}{}! Fast mode: Reading from database{}",
            BOLD, "\x1b[31m", RESET
        );
        println!();
    }

    if let Some(range) = date_range {
        println!("{}Data range: {}{}{}", DIM, RESET, CYAN, range);
        println!("{}", RESET);
    }

    println!(
        "{}Tip: View yearly heatmap with {}{}ccg export --open{}",
        DIM, RESET, CYAN, RESET
    );
}


/// Anonymize project folder names.
pub fn anonymize_projects(records: &[UsageRecord]) -> Vec<UsageRecord> {
    // Calculate total tokens per project
    let mut project_totals: HashMap<String, i64> = HashMap::new();
    for record in records {
        if let Some(usage) = &record.token_usage {
            *project_totals.entry(record.folder.clone()).or_insert(0) += usage.total_tokens();
        }
    }

    // Sort projects by total tokens (descending) and create mapping
    let mut sorted_projects: Vec<_> = project_totals.into_iter().collect();
    sorted_projects.sort_by(|a, b| b.1.cmp(&a.1));

    let project_mapping: HashMap<String, String> = sorted_projects
        .into_iter()
        .enumerate()
        .map(|(i, (folder, _))| (folder, format!("project-{:03}", i + 1)))
        .collect();

    // Replace folder names in records
    records
        .iter()
        .map(|record| {
            let mut new_record = record.clone();
            if let Some(anon_name) = project_mapping.get(&record.folder) {
                new_record.folder = anon_name.clone();
            }
            new_record
        })
        .collect()
}
