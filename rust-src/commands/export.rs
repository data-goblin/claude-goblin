//! Export command for heatmap generation.

use std::collections::HashMap;
use std::path::PathBuf;

use anyhow::Result;
use chrono::Local;

use crate::config::{get_db_path, get_claude_jsonl_files};
use crate::data::parse_jsonl_file;
use crate::storage::{save_snapshot, load_historical_records, get_database_stats};
use crate::visualization::{export_heatmap_svg, export_heatmap_png, open_file, DayStats};


/// Run the export command.
pub fn run(
    svg: bool,
    should_open: bool,
    fast: bool,
    year: Option<i32>,
    output: Option<String>,
) -> Result<()> {
    let db_path = get_db_path();

    // Check for fast mode with no database
    if fast && !db_path.exists() {
        eprintln!("Error: Cannot use --fast flag without existing database.");
        eprintln!("Run 'ccg usage' or 'ccg update usage' first to create the database.");
        return Ok(());
    }

    // Determine year
    let display_year = year.unwrap_or_else(|| Local::now().format("%Y").to_string().parse().unwrap());

    // Determine format and output path
    let format_type = if svg { "svg" } else { "png" };
    let output_path = if let Some(path) = output {
        PathBuf::from(path)
    } else {
        let default_dir = dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(".claude")
            .join("usage");
        std::fs::create_dir_all(&default_dir)?;
        default_dir.join(format!("claude-usage.{}", format_type))
    };

    // Fast mode warning
    if fast {
        let stats = get_database_stats(&db_path)?;
        if let Some(newest) = stats.newest_date {
            println!("\x1b[1m\x1b[31m! Fast mode: Reading from last update ({})\x1b[0m", newest);
        } else {
            println!("\x1b[1m\x1b[31m! Fast mode: Reading from database\x1b[0m");
        }
    }

    // Update data unless in fast mode
    if !fast {
        println!("Updating usage data...");

        let jsonl_files = match get_claude_jsonl_files() {
            Ok(files) => files,
            Err(e) => {
                eprintln!("Error: {}", e);
                return Ok(());
            }
        };

        if !jsonl_files.is_empty() {
            let mut all_records = Vec::new();
            for file in &jsonl_files {
                if let Ok(records) = parse_jsonl_file(file) {
                    all_records.extend(records);
                }
            }

            if !all_records.is_empty() {
                let _ = save_snapshot(&all_records, &db_path);
            }
        }
    }

    // Load data
    println!("Loading data for {}...", display_year);
    let records = load_historical_records(&db_path)?;

    if records.is_empty() {
        println!("No usage data found. Run 'ccg usage' to ingest data first.");
        return Ok(());
    }

    // Aggregate by day
    let mut daily_stats: HashMap<String, DayStats> = HashMap::new();
    for record in &records {
        let date_key = record.date_key();

        // Filter by year
        if !date_key.starts_with(&display_year.to_string()) {
            continue;
        }

        let entry = daily_stats.entry(date_key).or_default();
        entry.total_tokens += record.token_usage.as_ref().map(|u| u.total_tokens()).unwrap_or(0);
        if record.is_user_prompt() {
            entry.total_prompts += 1;
        }
    }

    if daily_stats.is_empty() {
        println!("No data found for year {}.", display_year);
        return Ok(());
    }

    // Export
    println!("Exporting to {}...", format_type.to_uppercase());

    if svg {
        export_heatmap_svg(&daily_stats, &output_path, Some(display_year), None)?;
    } else {
        export_heatmap_png(&daily_stats, &output_path, Some(display_year), None)?;
    }

    println!("\x1b[32m+ Exported to: {}\x1b[0m", output_path.display());

    // Open if requested
    if should_open {
        println!("Opening {}...", format_type.to_uppercase());
        open_file(&output_path)?;
    }

    Ok(())
}
