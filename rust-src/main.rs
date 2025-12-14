//! Claude Goblin CLI - Rust implementation
//!
//! Usage tracking and analytics for Claude Code.

mod cli;
mod config;
mod data;
mod models;
mod storage;


fn main() {
    if let Err(e) = cli::run() {
        eprintln!("Error: {e}");
        std::process::exit(1);
    }
}
