//! Status bar command for macOS menu bar app.

use anyhow::Result;

use crate::config::get_db_path;
use crate::storage::get_database_stats;


/// Run the status bar app.
pub fn run() -> Result<()> {
    #[cfg(not(target_os = "macos"))]
    {
        println!("\x1b[31mError: status-bar is only available on macOS\x1b[0m");
        return Ok(());
    }

    #[cfg(target_os = "macos")]
    {
        run_macos_status_bar()
    }
}


#[cfg(target_os = "macos")]
fn run_macos_status_bar() -> Result<()> {
    use tray_icon::{
        menu::{Menu, MenuEvent, MenuItem},
        TrayIconBuilder,
    };

    println!("\x1b[32mLaunching status bar app...\x1b[0m");
    println!("\x1b[2mThe app will appear in your menu bar showing token usage.\x1b[0m");
    println!("\x1b[2mPress Ctrl+C or select 'Quit' from the menu to stop.\x1b[0m\n");

    // Get initial stats
    let db_path = get_db_path();
    let stats = get_database_stats(&db_path).unwrap_or_default();

    let title = format_title(stats.total_tokens);

    // Create menu
    let menu = Menu::new();
    let refresh_item = MenuItem::new("Refresh", true, None);
    let quit_item = MenuItem::new("Quit", true, None);

    menu.append(&refresh_item)?;
    menu.append(&quit_item)?;

    // Create tray icon
    let _tray = TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_title(&title)
        .build()?;

    println!("Status bar active. Showing: {}", title);

    // Event loop
    let menu_channel = MenuEvent::receiver();

    loop {
        if let Ok(event) = menu_channel.try_recv() {
            if event.id == quit_item.id() {
                println!("\nQuitting status bar...");
                break;
            } else if event.id == refresh_item.id() {
                let stats = get_database_stats(&db_path).unwrap_or_default();
                let new_title = format_title(stats.total_tokens);
                println!("Refreshed: {}", new_title);
            }
        }

        std::thread::sleep(std::time::Duration::from_millis(100));
    }

    Ok(())
}


/// Format the title for the status bar.
fn format_title(total_tokens: i64) -> String {
    if total_tokens >= 1_000_000_000 {
        format!("CC: {:.1}B", total_tokens as f64 / 1_000_000_000.0)
    } else if total_tokens >= 1_000_000 {
        format!("CC: {:.1}M", total_tokens as f64 / 1_000_000.0)
    } else if total_tokens >= 1_000 {
        format!("CC: {:.1}K", total_tokens as f64 / 1_000.0)
    } else {
        format!("CC: {}", total_tokens)
    }
}
