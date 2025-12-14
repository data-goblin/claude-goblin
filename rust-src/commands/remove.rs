//! Remove subcommands.

use std::fs;
use std::io::{self, Write};

use anyhow::Result;

use crate::config::get_db_path;


/// Remove usage database.
pub fn usage(force: bool) -> Result<()> {
    let db_path = get_db_path();

    if !db_path.exists() {
        println!("\x1b[33mNo usage database found at {}\x1b[0m", db_path.display());
        return Ok(());
    }

    // Get file size
    let metadata = fs::metadata(&db_path)?;
    let size_kb = metadata.len() / 1024;

    println!("\x1b[1m\x1b[36mRemoving usage database\x1b[0m\n");
    println!("Database: {}", db_path.display());
    println!("Size: {} KB", size_kb);

    if !force {
        println!("\n\x1b[1m\x1b[31mWARNING: This will permanently delete all historical usage data!\x1b[0m");
        println!("\x1b[33mThis action cannot be undone.\x1b[0m\n");

        print!("Type 'delete' to confirm: ");
        io::stdout().flush()?;

        let mut input = String::new();
        io::stdin().read_line(&mut input)?;

        if input.trim().to_lowercase() != "delete" {
            println!("\x1b[33mCancelled\x1b[0m");
            return Ok(());
        }
    }

    // Create backup before deletion
    let backup_path = db_path.with_extension("db.bak");
    fs::copy(&db_path, &backup_path)?;
    println!("\n\x1b[2mBackup created: {}\x1b[0m", backup_path.display());

    // Delete database
    fs::remove_file(&db_path)?;

    println!("\x1b[32m+ Usage database deleted\x1b[0m");
    println!("\x1b[2mTo restore: ccg restore usage\x1b[0m");

    Ok(())
}
