//! Usage dashboard command.

use std::thread;
use std::time::Duration;

use anyhow::Result;

use crate::aggregation::calculate_overall_stats;
use crate::config::{get_claude_jsonl_files, get_db_path, DEFAULT_REFRESH_INTERVAL};
use crate::data::parse_jsonl_file;
use crate::storage::{save_snapshot, get_database_stats};
use crate::visualization::{render_dashboard, anonymize_projects};


/// Run the usage command.
pub fn run(live: bool, fast: bool, anon: bool) -> Result<()> {
    let db_path = get_db_path();

    // Check for fast mode with no database
    if fast && !db_path.exists() {
        eprintln!("Error: Cannot use --fast flag without existing database.");
        eprintln!("Run 'ccg usage' (without --fast) first to create the database.");
        return Ok(());
    }

    // Get JSONL files
    let jsonl_files = match get_claude_jsonl_files() {
        Ok(files) => files,
        Err(e) => {
            eprintln!("Error: {}", e);
            return Ok(());
        }
    };

    if jsonl_files.is_empty() {
        println!("No Claude Code data found. Make sure you've used Claude Code at least once.");
        return Ok(());
    }

    println!("Found {} session files", jsonl_files.len());

    if live {
        run_live_dashboard(&jsonl_files, fast, anon)?;
    } else {
        display_dashboard(&jsonl_files, fast, anon)?;
    }

    Ok(())
}


/// Run dashboard with auto-refresh.
fn run_live_dashboard(
    jsonl_files: &[std::path::PathBuf],
    fast: bool,
    anon: bool,
) -> Result<()> {
    println!(
        "Auto-refreshing every {} seconds. Press Ctrl+C to exit.\n",
        DEFAULT_REFRESH_INTERVAL
    );

    loop {
        display_dashboard(jsonl_files, fast, anon)?;
        thread::sleep(Duration::from_secs(DEFAULT_REFRESH_INTERVAL));
    }
}


/// Display the dashboard once.
fn display_dashboard(
    jsonl_files: &[std::path::PathBuf],
    fast: bool,
    anon: bool,
) -> Result<()> {
    let db_path = get_db_path();

    // Update data unless in fast mode
    if !fast {
        println!("Updating usage data...");

        let mut all_records = Vec::new();
        for file in jsonl_files {
            if let Ok(records) = parse_jsonl_file(file) {
                all_records.extend(records);
            }
        }

        if !all_records.is_empty() {
            let _ = save_snapshot(&all_records, &db_path);
        }
    }

    // Load records from database for display
    // For now, we'll use the parsed records directly since we don't have load_historical_records
    // implemented in Rust yet. In fast mode, we'll show stats from database.

    let records = if fast {
        // In fast mode, show database stats only
        let stats = get_database_stats(&db_path)?;

        // Create a simple stats-based display
        println!("\x1b[2J\x1b[H"); // Clear screen

        println!("┌────────────────────────────────────────────────────────────────────────────┐");
        println!("│                         Claude Code Usage Dashboard                        │");
        println!("└────────────────────────────────────────────────────────────────────────────┘");
        println!();

        // KPI Section
        let width = 28;
        let border = "─".repeat(width - 2);

        println!(
            "┌{}┐  ┌{}┐  ┌{}┐",
            border, border, border
        );
        println!(
            "│{:^26}│  │{:^26}│  │{:^26}│",
            "Total Tokens", "Prompts Sent", "Active Sessions"
        );
        println!(
            "│{:^26}│  │{:^26}│  │{:^26}│",
            format_number(stats.total_tokens),
            format_number(stats.total_prompts),
            format_number(stats.total_sessions),
        );
        println!(
            "└{}┘  └{}┘  └{}┘",
            border, border, border
        );

        println!();
        println!("\x1b[1m\x1b[31m! Fast mode: Reading from database\x1b[0m");
        println!();
        println!("\x1b[2mTip: View yearly heatmap with \x1b[0m\x1b[36mccg export --open\x1b[0m");

        return Ok(());
    } else {
        // Parse all records
        let mut all_records = Vec::new();
        for file in jsonl_files {
            if let Ok(records) = parse_jsonl_file(file) {
                all_records.extend(records);
            }
        }
        all_records
    };

    if records.is_empty() {
        println!("No usage data found. Run 'ccg update usage' to ingest data.");
        return Ok(());
    }

    // Get date range
    let mut dates: Vec<String> = records.iter().map(|r| r.date_key()).collect();
    dates.sort();
    dates.dedup();
    let date_range = if !dates.is_empty() {
        Some(format!("{} to {}", dates.first().unwrap(), dates.last().unwrap()))
    } else {
        None
    };

    // Anonymize if requested
    let display_records = if anon {
        anonymize_projects(&records)
    } else {
        records
    };

    // Calculate stats
    let stats = calculate_overall_stats(&display_records);

    // Render dashboard
    render_dashboard(
        &stats,
        &display_records,
        date_range.as_deref(),
        fast,
        true, // clear_screen
    );

    Ok(())
}


/// Format number with suffix.
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
