//! Claude Goblin CLI - Rust implementation
//!
//! Usage tracking and analytics for Claude Code.

mod aggregation;
mod cli;
mod commands;
mod config;
mod data;
mod hooks;
mod models;
mod storage;
mod visualization;


fn main() {
    if let Err(e) = cli::run() {
        eprintln!("Error: {e}");
        std::process::exit(1);
    }
}
