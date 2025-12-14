//! Restore subcommands.

use std::fs;

use anyhow::Result;

use crate::config::get_db_path;


/// Restore usage database from backup.
pub fn usage() -> Result<()> {
    let db_path = get_db_path();
    let backup_path = db_path.with_extension("db.bak");

    println!("\x1b[1m\x1b[36mRestoring usage database\x1b[0m\n");

    if !backup_path.exists() {
        println!("\x1b[31mNo backup found at {}\x1b[0m", backup_path.display());
        println!("\x1b[2mBackups are created when you run 'ccg remove usage'.\x1b[0m");
        return Ok(());
    }

    // Get backup file info
    let metadata = fs::metadata(&backup_path)?;
    let size_kb = metadata.len() / 1024;

    println!("Backup: {}", backup_path.display());
    println!("Size: {} KB", size_kb);

    if db_path.exists() {
        println!("\n\x1b[33mWarning: Current database will be overwritten.\x1b[0m");
    }

    // Restore from backup
    fs::copy(&backup_path, &db_path)?;

    println!("\n\x1b[32m+ Usage database restored from backup\x1b[0m");
    println!("Database: {}", db_path.display());

    Ok(())
}
