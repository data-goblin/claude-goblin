//! Stats command - show detailed statistics.

use anyhow::Result;
use chrono::{Datelike, NaiveDate};
use std::collections::HashSet;

use crate::config::{get_claude_jsonl_files, get_db_path};
use crate::data::parse_jsonl_file;
use crate::storage::{get_database_stats, save_snapshot};


/// Run the stats command.
pub fn run(fast: bool) -> Result<()> {
    let db_path = get_db_path();

    // Check for fast mode with no database
    if fast && !db_path.exists() {
        eprintln!("Error: Cannot use --fast flag without existing database.");
        eprintln!("Run 'ccg stats' (without --fast) first to create the database.");
        return Ok(());
    }

    // Update data unless in fast mode
    if !fast {
        println!("Updating database...");
        if let Ok(jsonl_files) = get_claude_jsonl_files() {
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
    } else {
        println!("Fast mode: Reading from database...\n");
    }

    // Get stats from database
    let stats = get_database_stats(&db_path)?;

    if stats.total_records == 0 && stats.total_prompts == 0 {
        println!("No historical data found. Run 'ccg update usage' to start tracking.");
        return Ok(());
    }

    // Header
    println!("\n{}", "=".repeat(60));
    println!("{:^60}", "Claude Code Usage Statistics");
    println!("{}\n", "=".repeat(60));

    // Summary Statistics
    println!("SUMMARY");
    println!("{}", "-".repeat(40));
    println!("  Total Tokens:        {:>15}", format_number(stats.total_tokens));
    println!("  Total Prompts:       {:>15}", format_number(stats.total_prompts));
    println!("  Total Responses:     {:>15}", format_number(stats.total_responses));
    println!("  Total Sessions:      {:>15}", format_number(stats.total_sessions));
    println!("  Days Tracked:        {:>15}", format_number(stats.total_days));

    if let (Some(oldest), Some(newest)) = (&stats.oldest_date, &stats.newest_date) {
        println!("  Date Range:          {} to {}", oldest, newest);
    }

    // Cost Analysis
    if stats.total_cost > 0.0 {
        println!("\nCOST ANALYSIS");
        println!("{}", "-".repeat(40));
        println!("  Est. Cost (API):     ${:>14}", format_currency(stats.total_cost));

        // Calculate months covered
        if let (Some(oldest), Some(newest)) = (&stats.oldest_date, &stats.newest_date) {
            if let (Ok(start), Ok(end)) = (
                NaiveDate::parse_from_str(oldest, "%Y-%m-%d"),
                NaiveDate::parse_from_str(newest, "%Y-%m-%d"),
            ) {
                let mut months = HashSet::new();
                let mut current = start;
                while current <= end {
                    months.insert((current.year(), current.month()));
                    current = current.checked_add_days(chrono::Days::new(1)).unwrap_or(end);
                }
                let num_months = months.len().max(1);
                let plan_cost = num_months as f64 * 200.0;
                let savings = stats.total_cost - plan_cost;

                println!(
                    "  Plan Cost:           ${:>14} ({} month{} @ $200/mo)",
                    format_currency(plan_cost),
                    num_months,
                    if num_months > 1 { "s" } else { "" }
                );

                if savings > 0.0 {
                    println!("  You Saved:           ${:>14} (vs API)", format_currency(savings));
                } else {
                    println!("  Plan Costs More:     ${:>14}", format_currency(savings.abs()));
                    println!("  [Light usage - API would be cheaper]");
                }
            }
        }
    }

    // Averages
    println!("\nAVERAGES");
    println!("{}", "-".repeat(40));
    let avg_per_session = if stats.total_sessions > 0 {
        stats.total_tokens / stats.total_sessions
    } else {
        0
    };
    let avg_per_response = if stats.total_responses > 0 {
        stats.total_tokens / stats.total_responses
    } else {
        0
    };
    println!("  Tokens per Session:  {:>15}", format_number(avg_per_session));
    println!("  Tokens per Response: {:>15}", format_number(avg_per_response));

    if stats.total_cost > 0.0 && stats.total_sessions > 0 {
        let cost_per_session = stats.total_cost / stats.total_sessions as f64;
        let cost_per_response = if stats.total_responses > 0 {
            stats.total_cost / stats.total_responses as f64
        } else {
            0.0
        };
        println!("  Cost per Session:    ${:>14}", format_currency(cost_per_session));
        println!("  Cost per Response:   ${:>14}", format_currency_4(cost_per_response));
    }

    // Tokens by Model
    if !stats.tokens_by_model.is_empty() {
        println!("\nUSAGE BY MODEL");
        println!("{}", "-".repeat(60));

        let mut models: Vec<_> = stats.tokens_by_model.iter().collect();
        models.sort_by(|a, b| b.1.cmp(a.1));

        for (model, tokens) in models {
            let percentage = if stats.total_tokens > 0 {
                (*tokens as f64 / stats.total_tokens as f64) * 100.0
            } else {
                0.0
            };
            let cost = stats.cost_by_model.get(model).copied().unwrap_or(0.0);

            if cost > 0.0 {
                println!(
                    "  {:30} {:>12} ({:5.1}%) ${:>10}",
                    model,
                    format_number(*tokens),
                    percentage,
                    format_currency(cost)
                );
            } else {
                println!(
                    "  {:30} {:>12} ({:5.1}%)",
                    model,
                    format_number(*tokens),
                    percentage
                );
            }
        }
    }

    // Database Info
    println!("\n{}", "-".repeat(60));
    println!("Database: ~/.claude/usage/usage_history.db");
    if stats.total_records > 0 {
        println!("Detail records: {} (full analytics mode)", format_number(stats.total_records));
    } else {
        println!("Storage mode: aggregate (daily totals only)");
    }

    Ok(())
}


/// Format a number with commas.
fn format_number(n: i64) -> String {
    let s = n.to_string();
    let mut result = String::new();
    let chars: Vec<char> = s.chars().collect();

    for (i, c) in chars.iter().enumerate() {
        if i > 0 && (chars.len() - i) % 3 == 0 {
            result.push(',');
        }
        result.push(*c);
    }

    result
}


/// Format currency with 2 decimal places and commas.
fn format_currency(n: f64) -> String {
    let formatted = format!("{:.2}", n);
    let parts: Vec<&str> = formatted.split('.').collect();
    let integer_part = parts[0];
    let decimal_part = parts.get(1).unwrap_or(&"00");

    let mut result = String::new();
    let chars: Vec<char> = integer_part.chars().collect();

    for (i, c) in chars.iter().enumerate() {
        if i > 0 && (chars.len() - i) % 3 == 0 {
            result.push(',');
        }
        result.push(*c);
    }

    format!("{}.{}", result, decimal_part)
}


/// Format currency with 4 decimal places.
fn format_currency_4(n: f64) -> String {
    format!("{:.4}", n)
}
