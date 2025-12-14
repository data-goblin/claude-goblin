//! Update usage data from JSONL files to database.

use anyhow::Result;

use crate::config::{get_claude_jsonl_files, get_db_path};
use crate::data::parse_jsonl_file;
use crate::storage::save_snapshot;


/// Run the update usage command.
pub fn run() -> Result<()> {
    println!("Updating usage database...");

    // Get JSONL files
    let jsonl_files = match get_claude_jsonl_files() {
        Ok(files) => files,
        Err(e) => {
            eprintln!("Error: {}", e);
            return Ok(());
        }
    };

    if jsonl_files.is_empty() {
        println!("No JSONL files found.");
        return Ok(());
    }

    println!("Found {} JSONL files", jsonl_files.len());

    // Parse all files and collect records
    let mut all_records = Vec::new();
    for file in &jsonl_files {
        match parse_jsonl_file(file) {
            Ok(records) => {
                all_records.extend(records);
            }
            Err(e) => {
                eprintln!("Warning: Error parsing {}: {}", file.display(), e);
            }
        }
    }

    println!("Parsed {} records", all_records.len());

    // Save to database
    let db_path = get_db_path();
    let saved = save_snapshot(&all_records, &db_path)?;

    println!("Saved {} new records to database", saved);
    println!("Database: {}", db_path.display());

    Ok(())
}
