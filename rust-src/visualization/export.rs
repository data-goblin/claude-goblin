//! Export functionality for heatmap visualizations.

use std::collections::HashMap;
use std::path::Path;

use anyhow::{Context, Result};
use chrono::{Datelike, Local, NaiveDate};


// Claude UI color scheme
const CLAUDE_BG: &str = "#262624";
const CLAUDE_TEXT: &str = "#FAF9F5";
const CLAUDE_TEXT_SECONDARY: &str = "#C2C0B7";
const CLAUDE_DARK_GREY: &str = "#3C3C3A";
const CLAUDE_LIGHT_GREY: &str = "#6B6B68";
const CLAUDE_ORANGE_RGB: (u8, u8, u8) = (203, 123, 93);

// Cell dimensions (scaled for sharp output)
const SCALE_FACTOR: i32 = 3;
const CELL_SIZE: i32 = 12 * SCALE_FACTOR;
const CELL_GAP: i32 = 3 * SCALE_FACTOR;
const CELL_TOTAL: i32 = CELL_SIZE + CELL_GAP;


/// Daily stats for heatmap rendering.
#[derive(Debug, Clone, Default)]
pub struct DayStats {
    pub total_tokens: i64,
    pub total_prompts: i64,
}


/// Export heatmap as SVG.
pub fn export_heatmap_svg(
    daily_stats: &HashMap<String, DayStats>,
    output_path: &Path,
    year: Option<i32>,
    title: Option<&str>,
) -> Result<()> {
    let display_year = year.unwrap_or_else(|| Local::now().year());
    let svg_content = generate_svg(daily_stats, display_year, title);

    std::fs::write(output_path, svg_content)
        .with_context(|| format!("Failed to write SVG to {}", output_path.display()))?;

    Ok(())
}


/// Export heatmap as PNG.
pub fn export_heatmap_png(
    daily_stats: &HashMap<String, DayStats>,
    output_path: &Path,
    year: Option<i32>,
    title: Option<&str>,
) -> Result<()> {
    let display_year = year.unwrap_or_else(|| Local::now().year());
    let svg_content = generate_svg(daily_stats, display_year, title);

    // Parse SVG
    let tree = resvg::usvg::Tree::from_str(
        &svg_content,
        &resvg::usvg::Options::default(),
    ).context("Failed to parse SVG")?;

    // Render to pixmap
    let size = tree.size();
    let width = size.width() as u32;
    let height = size.height() as u32;

    let mut pixmap = tiny_skia::Pixmap::new(width, height)
        .context("Failed to create pixmap")?;

    // Fill with background color
    let bg = hex_to_rgb(CLAUDE_BG);
    pixmap.fill(tiny_skia::Color::from_rgba8(bg.0, bg.1, bg.2, 255));

    // Render SVG
    resvg::render(&tree, tiny_skia::Transform::identity(), &mut pixmap.as_mut());

    // Save as PNG
    pixmap.save_png(output_path)
        .with_context(|| format!("Failed to save PNG to {}", output_path.display()))?;

    Ok(())
}


/// Generate SVG content for the heatmap.
fn generate_svg(
    daily_stats: &HashMap<String, DayStats>,
    year: i32,
    title: Option<&str>,
) -> String {
    let today = Local::now().date_naive();
    let start_date = NaiveDate::from_ymd_opt(year, 1, 1).unwrap();
    let end_date = NaiveDate::from_ymd_opt(year, 12, 31).unwrap();

    // Build weeks structure
    let jan1_day = start_date.weekday().num_days_from_sunday() as usize;
    let mut weeks: Vec<Vec<Option<NaiveDate>>> = Vec::new();
    let mut current_week: Vec<Option<NaiveDate>> = Vec::new();

    // Pad first week with None
    for _ in 0..jan1_day {
        current_week.push(None);
    }

    // Add all days
    let mut current_date = start_date;
    while current_date <= end_date {
        current_week.push(Some(current_date));

        if current_week.len() == 7 {
            weeks.push(current_week);
            current_week = Vec::new();
        }

        current_date = current_date.succ_opt().unwrap();
    }

    // Pad final week
    if !current_week.is_empty() {
        while current_week.len() < 7 {
            current_week.push(None);
        }
        weeks.push(current_week);
    }

    // Calculate dimensions
    let num_weeks = weeks.len() as i32;
    let width = (num_weeks * CELL_TOTAL) + 120;
    let height = (7 * CELL_TOTAL) + 80;

    // Calculate max tokens for scaling
    let max_tokens = daily_stats.values()
        .map(|s| s.total_tokens)
        .max()
        .unwrap_or(1)
        .max(1);

    let default_title = format!("Your Claude Code activity in {}", year);
    let display_title = title.unwrap_or(&default_title);

    let mut svg_parts = vec![
        format!(r#"<svg width="{}" height="{}" xmlns="http://www.w3.org/2000/svg">"#, width, height),
        "<style>".to_string(),
        format!("  .day-cell {{ stroke: {}; stroke-width: 1; }}", CLAUDE_BG),
        format!("  .month-label {{ fill: {}; font: 12px -apple-system, sans-serif; }}", CLAUDE_TEXT_SECONDARY),
        format!("  .day-label {{ fill: {}; font: 10px -apple-system, sans-serif; }}", CLAUDE_TEXT_SECONDARY),
        format!("  .title {{ fill: {}; font: bold 16px -apple-system, sans-serif; }}", CLAUDE_TEXT),
        format!("  .legend-text {{ fill: {}; font: 10px -apple-system, sans-serif; }}", CLAUDE_TEXT_SECONDARY),
        "</style>".to_string(),
        format!(r#"<rect width="{}" height="{}" fill="{}"/>"#, width, height, CLAUDE_BG),
    ];

    // Draw Claude guy icon
    svg_parts.push(generate_clawd_svg(10, 10, 3));

    // Title
    let title_x = 10 + (8 * 3) + 8;
    svg_parts.push(format!(r#"<text x="{}" y="25" class="title">{}</text>"#, title_x, display_title));

    // Day labels
    let day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    for (day_idx, day_name) in day_names.iter().enumerate() {
        let y = 60 + (day_idx as i32 * CELL_TOTAL) + (CELL_SIZE / 2);
        svg_parts.push(format!(
            r#"<text x="5" y="{}" class="day-label" text-anchor="start">{}</text>"#,
            y + 4, day_name
        ));
    }

    // Month labels
    let mut last_month = 0u32;
    for (week_idx, week) in weeks.iter().enumerate() {
        for date in week.iter().flatten() {
            let month = date.month();
            if month != last_month {
                let x = 40 + (week_idx as i32 * CELL_TOTAL);
                let month_name = month_abbrev(month);
                svg_parts.push(format!(
                    r#"<text x="{}" y="50" class="month-label">{}</text>"#,
                    x, month_name
                ));
                last_month = month;
            }
            break;
        }
    }

    // Heatmap cells
    for (week_idx, week) in weeks.iter().enumerate() {
        for (day_idx, date_opt) in week.iter().enumerate() {
            let Some(date) = date_opt else { continue };

            let x = 40 + (week_idx as i32 * CELL_TOTAL);
            let y = 60 + (day_idx as i32 * CELL_TOTAL);

            let date_key = date.format("%Y-%m-%d").to_string();
            let day_stats = daily_stats.get(&date_key);

            let color = get_cell_color(day_stats, max_tokens, *date, today);

            // Tooltip
            let tooltip = if let Some(stats) = day_stats {
                if stats.total_tokens > 0 {
                    format!("{}: {} prompts, {} tokens", date, stats.total_prompts, format_number(stats.total_tokens))
                } else {
                    format!("{}: No activity", date)
                }
            } else if *date > today {
                format!("{}: Future", date)
            } else {
                format!("{}: No activity", date)
            };

            svg_parts.push(format!(
                r#"<rect x="{}" y="{}" width="{}" height="{}" fill="{}" class="day-cell"><title>{}</title></rect>"#,
                x, y, CELL_SIZE, CELL_SIZE, color, tooltip
            ));
        }
    }

    // Legend
    let legend_y = height - 20;
    let legend_x = 40;
    svg_parts.push(format!(r#"<text x="{}" y="{}" class="legend-text">Less</text>"#, legend_x, legend_y));

    // Gradient squares
    for i in 0..5 {
        let intensity = 0.2 + (i as f64 / 4.0) * 0.8;
        let r = (CLAUDE_ORANGE_RGB.0 as f64 * intensity) as u8;
        let g = (CLAUDE_ORANGE_RGB.1 as f64 * intensity) as u8;
        let b = (CLAUDE_ORANGE_RGB.2 as f64 * intensity) as u8;
        let color = format!("rgb({},{},{})", r, g, b);
        let x = legend_x + 35 + (i * (CELL_SIZE + 2));
        svg_parts.push(format!(
            r#"<rect x="{}" y="{}" width="{}" height="{}" fill="{}" class="day-cell"/>"#,
            x, legend_y - CELL_SIZE + 2, CELL_SIZE, CELL_SIZE, color
        ));
    }

    svg_parts.push(format!(
        r#"<text x="{}" y="{}" class="legend-text">More</text>"#,
        legend_x + 35 + (5 * (CELL_SIZE + 2)) + 5, legend_y
    ));

    svg_parts.push("</svg>".to_string());

    svg_parts.join("\n")
}


/// Get cell color based on activity level.
fn get_cell_color(day_stats: Option<&DayStats>, max_tokens: i64, date: NaiveDate, today: NaiveDate) -> String {
    // Future days: light grey
    if date > today {
        return CLAUDE_LIGHT_GREY.to_string();
    }

    // Past days with no activity: dark grey
    let tokens = day_stats.map(|s| s.total_tokens).unwrap_or(0);
    if tokens == 0 {
        return CLAUDE_DARK_GREY.to_string();
    }

    // Calculate intensity ratio
    let ratio = (tokens as f64 / max_tokens as f64).sqrt(); // Non-linear scaling

    // Interpolate from dark grey to orange
    let dark = hex_to_rgb(CLAUDE_DARK_GREY);
    let r = (dark.0 as f64 + (CLAUDE_ORANGE_RGB.0 as f64 - dark.0 as f64) * ratio) as u8;
    let g = (dark.1 as f64 + (CLAUDE_ORANGE_RGB.1 as f64 - dark.1 as f64) * ratio) as u8;
    let b = (dark.2 as f64 + (CLAUDE_ORANGE_RGB.2 as f64 - dark.2 as f64) * ratio) as u8;

    format!("rgb({},{},{})", r, g, b)
}


/// Generate SVG for Claude guy (Clawd) icon.
fn generate_clawd_svg(x: i32, y: i32, pixel_size: i32) -> String {
    let orange = format!("rgb({},{},{})", CLAUDE_ORANGE_RGB.0, CLAUDE_ORANGE_RGB.1, CLAUDE_ORANGE_RGB.2);
    let dark_grey = CLAUDE_DARK_GREY;

    // Pixel grid: 1 = orange, 0 = transparent, 2 = dark grey (eyes)
    let grid = [
        [1, 1, 1, 1, 1, 1, 1, 1],
        [0, 1, 2, 1, 1, 2, 1, 0],
        [0, 1, 1, 1, 1, 1, 1, 0],
        [0, 1, 1, 0, 0, 1, 1, 0],
    ];

    let mut parts = Vec::new();
    for (row_idx, row) in grid.iter().enumerate() {
        for (col_idx, &pixel_type) in row.iter().enumerate() {
            if pixel_type == 0 {
                continue;
            }

            let color = if pixel_type == 1 { &orange } else { dark_grey };
            let px = x + (col_idx as i32 * pixel_size);
            let py = y + (row_idx as i32 * pixel_size);

            parts.push(format!(
                r#"<rect x="{}" y="{}" width="{}" height="{}" fill="{}"/>"#,
                px, py, pixel_size, pixel_size, color
            ));
        }
    }

    parts.join("\n")
}


/// Convert hex color to RGB tuple.
fn hex_to_rgb(hex: &str) -> (u8, u8, u8) {
    let hex = hex.trim_start_matches('#');
    let r = u8::from_str_radix(&hex[0..2], 16).unwrap_or(0);
    let g = u8::from_str_radix(&hex[2..4], 16).unwrap_or(0);
    let b = u8::from_str_radix(&hex[4..6], 16).unwrap_or(0);
    (r, g, b)
}


/// Get month abbreviation.
fn month_abbrev(month: u32) -> &'static str {
    match month {
        1 => "Jan",
        2 => "Feb",
        3 => "Mar",
        4 => "Apr",
        5 => "May",
        6 => "Jun",
        7 => "Jul",
        8 => "Aug",
        9 => "Sep",
        10 => "Oct",
        11 => "Nov",
        12 => "Dec",
        _ => "",
    }
}


/// Format number with suffix.
fn format_number(num: i64) -> String {
    if num >= 1_000_000_000 {
        format!("{:.1}B", num as f64 / 1_000_000_000.0)
    } else if num >= 1_000_000 {
        format!("{:.1}M", num as f64 / 1_000_000.0)
    } else if num >= 1_000 {
        format!("{:.1}K", num as f64 / 1_000.0)
    } else {
        format!("{}", num)
    }
}


/// Open file with default application.
pub fn open_file(path: &Path) -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(path)
            .spawn()
            .context("Failed to open file")?;
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(["/C", "start", "", &path.to_string_lossy()])
            .spawn()
            .context("Failed to open file")?;
    }

    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(path)
            .spawn()
            .context("Failed to open file")?;
    }

    Ok(())
}
