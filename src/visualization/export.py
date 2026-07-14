#region Imports
from datetime import date as date_type
from datetime import datetime, timedelta
from pathlib import Path

from src.aggregation.daily_stats import AggregatedStats, DailyStats

#endregion


#region Constants
# Claude UI color scheme
CLAUDE_BG = "#262624"
CLAUDE_TEXT = "#FAF9F5"
CLAUDE_TEXT_SECONDARY = "#C2C0B7"
CLAUDE_DARK_GREY = "#3C3C3A"  # Past days with no activity
CLAUDE_LIGHT_GREY = "#6B6B68"  # Future days
CLAUDE_ORANGE_RGB = (203, 123, 93)  # #CB7B5D

# Export at higher resolution for sharp output
SCALE_FACTOR = 3  # 3x resolution
CELL_SIZE = 12 * SCALE_FACTOR
CELL_GAP = 3 * SCALE_FACTOR
CELL_TOTAL = CELL_SIZE + CELL_GAP
#endregion


#region Functions


def export_heatmap_svg(
    stats: AggregatedStats,
    output_path: Path,
    title: str | None = None,
    year: int | None = None
) -> None:
    """
    Export the activity heatmap as an SVG file.

    Args:
        stats: Aggregated statistics to visualize
        output_path: Path where SVG file will be saved
        title: Optional title for the graph
        year: Year to display (defaults to current year)

    Raises:
        IOError: If file cannot be written
    """
    # Show full year: Jan 1 to Dec 31
    today = datetime.now().date()
    display_year = year if year is not None else today.year
    start_date = datetime(display_year, 1, 1).date()
    end_date = datetime(display_year, 12, 31).date()

    # Build weeks structure
    jan1_day = (start_date.weekday() + 1) % 7
    weeks: list[list[tuple[DailyStats | None, date_type | None]]] = []
    current_week: list[tuple[DailyStats | None, date_type | None]] = []

    # Pad first week with None
    for _ in range(jan1_day):
        current_week.append((None, None))

    # Add all days from Jan 1 to Dec 31
    current_date = start_date
    while current_date <= end_date:
        date_key = current_date.strftime("%Y-%m-%d")
        day_stats = stats.daily_stats.get(date_key)
        current_week.append((day_stats, current_date))

        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []

        current_date += timedelta(days=1)

    # Pad final week with None
    if current_week:
        while len(current_week) < 7:
            current_week.append((None, None))
        weeks.append(current_week)

    # Calculate dimensions
    num_weeks = len(weeks)
    width = (num_weeks * CELL_TOTAL) + 120  # Extra space for labels
    height = (7 * CELL_TOTAL) + 80  # Extra space for title and legend

    # Calculate max tokens for scaling
    max_tokens = max(
        (s.total_tokens for s in stats.daily_stats.values()), default=1
    ) if stats.daily_stats else 1

    # Generate SVG with dynamic title
    default_title = f"Your Claude Code activity in {display_year}"
    svg = _generate_svg(weeks, width, height, max_tokens, title or default_title)

    # Write to file
    output_path.write_text(svg, encoding="utf-8")


def export_heatmap_png(
    stats: AggregatedStats,
    output_path: Path,
    title: str | None = None,
    year: int | None = None,
) -> None:
    """
    Export the token activity heatmap as a PNG file.

    Requires Pillow: pip install pillow

    Args:
        stats: Aggregated statistics to visualize
        output_path: Path where PNG file will be saved
        title: Optional title for the graph
        year: Year to display (defaults to current year)

    Raises:
        ImportError: If Pillow is not installed
        IOError: If file cannot be written
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise ImportError(
            "PNG export requires Pillow. "
            "Install with: pip install pillow"
        )

    # Build weeks structure (same as SVG)
    today = datetime.now().date()
    display_year = year if year is not None else today.year
    start_date = datetime(display_year, 1, 1).date()
    end_date = datetime(display_year, 12, 31).date()

    jan1_day = (start_date.weekday() + 1) % 7
    weeks: list[list[tuple[DailyStats | None, date_type | None]]] = []
    current_week: list[tuple[DailyStats | None, date_type | None]] = []

    for _ in range(jan1_day):
        current_week.append((None, None))

    current_date = start_date
    while current_date <= end_date:
        date_key = current_date.strftime("%Y-%m-%d")
        day_stats = stats.daily_stats.get(date_key)
        current_week.append((day_stats, current_date))

        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []

        current_date += timedelta(days=1)

    if current_week:
        while len(current_week) < 7:
            current_week.append((None, None))
        weeks.append(current_week)

    # Calculate dimensions
    num_weeks = len(weeks)

    # Base grid dimensions (one heatmap)
    grid_width = num_weeks * CELL_TOTAL
    grid_height = 7 * CELL_TOTAL

    # Layout: Vertical stack with titles and legends for each
    base_padding = int(40 * SCALE_FACTOR * 0.66)
    day_label_space = 35 * SCALE_FACTOR
    heatmap_vertical_gap = 40 * SCALE_FACTOR  # Gap between vertically stacked heatmaps
    heatmap_title_space = 20 * SCALE_FACTOR  # Space for individual heatmap titles
    month_label_space = 12 * SCALE_FACTOR  # Space for month labels above each grid
    legend_height = CELL_SIZE + (8 * SCALE_FACTOR)  # Legend squares + small buffer

    # Main title at the top
    main_title_height = 20 * SCALE_FACTOR
    main_title_to_first_heatmap = 25 * SCALE_FACTOR

    # Each heatmap section includes: title + month labels + grid + legend
    single_heatmap_section_height = heatmap_title_space + month_label_space + grid_height + legend_height
    num_heatmaps = 1

    # Total height
    top_padding = base_padding + main_title_height + main_title_to_first_heatmap
    content_height = (num_heatmaps * single_heatmap_section_height) + ((num_heatmaps - 1) * heatmap_vertical_gap)
    bottom_padding = base_padding

    width = base_padding + day_label_space + grid_width + base_padding
    height = top_padding + content_height + bottom_padding

    # Calculate max tokens
    max_tokens = max(
        (s.total_tokens for s in stats.daily_stats.values()), default=1
    ) if stats.daily_stats else 1

    # Create image
    img = Image.new('RGB', (width, height), _hex_to_rgb(CLAUDE_BG))
    draw = ImageDraw.Draw(img)

    # Try to load a system font with scaled sizes (cross-platform)
    try:
        # Try common font paths across different systems
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
            "C:\\Windows\\Fonts\\arial.ttf",  # Windows
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Linux alternative
        ]

        title_font = None
        label_font = None

        for font_path in font_paths:
            try:
                title_font = ImageFont.truetype(font_path, 16 * SCALE_FACTOR)
                label_font = ImageFont.truetype(font_path, 10 * SCALE_FACTOR)
                break
            except:
                continue

        if title_font is None:
            raise Exception("No system font found")
    except:
        title_font = ImageFont.load_default()
        label_font = ImageFont.load_default()

    # Calculate common X positions
    day_label_x = base_padding
    grid_x = base_padding + day_label_space

    # Calculate Y positions for each heatmap section dynamically
    heatmap_y_positions = []
    current_y = top_padding
    for i in range(num_heatmaps):
        heatmap_y_positions.append(current_y)
        current_y += single_heatmap_section_height + heatmap_vertical_gap

    # Draw main title and icon at the very top
    title_x = base_padding
    title_y = base_padding
    pixel_size = int(SCALE_FACTOR * 4)
    icon_width = _draw_claude_guy(draw, title_x, title_y, pixel_size)
    title_text_x = title_x + icon_width + (8 * SCALE_FACTOR)
    default_title = f"Your Claude Code activity in {display_year}"
    draw.text((title_text_x, title_y), title or default_title, fill=_hex_to_rgb(CLAUDE_TEXT), font=title_font)

    corner_radius = 2 * SCALE_FACTOR
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    # Helper function to draw one complete heatmap section
    def draw_heatmap_section(section_y_start, heatmap_title, gradient_func):
        # Positions within this section
        title_y = section_y_start
        month_y = title_y + heatmap_title_space
        grid_y = month_y + month_label_space
        legend_y = grid_y + grid_height + (CELL_GAP * 2)
        legend_square_y = legend_y - (CELL_SIZE // 4)

        # Draw heatmap title
        draw.text((grid_x, title_y), heatmap_title, fill=_hex_to_rgb(CLAUDE_TEXT_SECONDARY), font=label_font)

        # Draw day labels (vertically centered with row)
        for day_idx, day_name in enumerate(day_names):
            y = grid_y + (day_idx * CELL_TOTAL) + (CELL_SIZE // 2)
            draw.text((day_label_x, y), day_name, fill=_hex_to_rgb(CLAUDE_TEXT_SECONDARY), font=label_font, anchor="lm")  # left-middle anchor

        # Draw month labels
        last_month = None
        for week_idx, week in enumerate(weeks):
            for day_stats, date in week:
                if date is not None:
                    month = date.month
                    if month != last_month:
                        x = grid_x + (week_idx * CELL_TOTAL)
                        month_name = date.strftime("%b")
                        draw.text((x, month_y), month_name, fill=_hex_to_rgb(CLAUDE_TEXT_SECONDARY), font=label_font)
                        last_month = month
                    break

        # Draw heatmap cells
        for week_idx, week in enumerate(weeks):
            for day_idx, (day_stats, date) in enumerate(week):
                if date is None:
                    continue

                x = grid_x + (week_idx * CELL_TOTAL)
                y = grid_y + (day_idx * CELL_TOTAL)

                color = gradient_func(day_stats, date)
                draw.rounded_rectangle([x, y, x + CELL_SIZE, y + CELL_SIZE],
                                        radius=corner_radius, fill=color, outline=_hex_to_rgb(CLAUDE_BG))

        # Draw legend: dark grey + orange gradient
        draw.text((grid_x, legend_y), "Less", fill=_hex_to_rgb(CLAUDE_TEXT_SECONDARY), font=label_font)
        text_bbox = draw.textbbox((grid_x, legend_y), "Less", font=label_font)
        text_width = text_bbox[2] - text_bbox[0]

        legend_extra_gap = int(CELL_GAP * 0.3)
        legend_square_spacing = CELL_SIZE + CELL_GAP + legend_extra_gap
        squares_start = grid_x + text_width + (CELL_GAP * 2)

        draw.rounded_rectangle([squares_start, legend_square_y, squares_start + CELL_SIZE, legend_square_y + CELL_SIZE],
                                radius=corner_radius, fill=_hex_to_rgb(CLAUDE_DARK_GREY))
        for i in range(1, 5):
            intensity = 0.2 + ((i - 1) / 3) * 0.8
            r = int(CLAUDE_ORANGE_RGB[0] * intensity)
            g = int(CLAUDE_ORANGE_RGB[1] * intensity)
            b = int(CLAUDE_ORANGE_RGB[2] * intensity)
            x = squares_start + (i * legend_square_spacing)
            draw.rounded_rectangle([x, legend_square_y, x + CELL_SIZE, legend_square_y + CELL_SIZE],
                                    radius=corner_radius, fill=(r, g, b))

        more_x = squares_start + (5 * legend_square_spacing) + CELL_GAP
        draw.text((more_x, legend_y), "More", fill=_hex_to_rgb(CLAUDE_TEXT_SECONDARY), font=label_font)

    def tokens_gradient(day_stats, date):
        color_str = _get_color(day_stats, max_tokens, date, today)
        return _parse_rgb(color_str) if color_str.startswith('rgb(') else _hex_to_rgb(color_str)

    draw_heatmap_section(heatmap_y_positions[0], "Token Usage", tokens_gradient)

    # Save image
    img.save(output_path, 'PNG')


def _generate_svg(
    weeks: list[list[tuple[DailyStats | None, date_type | None]]],
    width: int,
    height: int,
    max_tokens: int,
    title: str
) -> str:
    """
    Generate SVG markup for the heatmap.

    Args:
        weeks: List of weeks with daily stats
        width: SVG width in pixels
        height: SVG height in pixels
        max_tokens: Maximum token count for scaling
        title: Title text

    Returns:
        SVG markup as a string
    """
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        '<style>',
        f'  .day-cell {{ stroke: {CLAUDE_BG}; stroke-width: 1; }}',
        f'  .month-label {{ fill: {CLAUDE_TEXT_SECONDARY}; font: 12px -apple-system, sans-serif; }}',
        f'  .day-label {{ fill: {CLAUDE_TEXT_SECONDARY}; font: 10px -apple-system, sans-serif; }}',
        f'  .title {{ fill: {CLAUDE_TEXT}; font: bold 16px -apple-system, sans-serif; }}',
        f'  .legend-text {{ fill: {CLAUDE_TEXT_SECONDARY}; font: 10px -apple-system, sans-serif; }}',
        '</style>',
        f'<rect width="{width}" height="{height}" fill="{CLAUDE_BG}"/>',
    ]

    # Draw Claude guy (Clawd) icon in SVG
    clawd_svg = _generate_clawd_svg(10, 10, 3)
    svg_parts.append(clawd_svg)

    # Title (positioned after Clawd icon)
    title_x = 10 + (8 * 3) + 8  # Icon width + gap
    svg_parts.append(f'<text x="{title_x}" y="25" class="title">{title}</text>')

    # Day labels (Y-axis)
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for day_idx, day_name in enumerate(day_names):
        y = 60 + (day_idx * CELL_TOTAL) + (CELL_SIZE // 2)
        svg_parts.append(f'<text x="5" y="{y + 4}" class="day-label" text-anchor="start">{day_name}</text>')

    # Month labels (X-axis)
    last_month = None
    for week_idx, week in enumerate(weeks):
        for day_stats, date in week:
            if date is not None:
                month = date.month
                if month != last_month:
                    x = 40 + (week_idx * CELL_TOTAL)
                    month_name = date.strftime("%b")
                    svg_parts.append(f'<text x="{x}" y="50" class="month-label">{month_name}</text>')
                    last_month = month
                break

    # Heatmap cells
    today = datetime.now().date()
    for week_idx, week in enumerate(weeks):
        for day_idx, (day_stats, date) in enumerate(week):
            if date is None:
                # Skip padding cells
                continue

            x = 40 + (week_idx * CELL_TOTAL)
            y = 60 + (day_idx * CELL_TOTAL)

            color = _get_color(day_stats, max_tokens, date, today)

            # Add tooltip with date and stats
            if day_stats and day_stats.total_tokens > 0:
                tooltip = f"{date}: {day_stats.total_prompts} prompts, {day_stats.total_tokens:,} tokens"
            elif date > today:
                tooltip = f"{date}: Future"
            else:
                tooltip = f"{date}: No activity"

            svg_parts.append(f'<rect x="{x}" y="{y}" width="{CELL_SIZE}" height="{CELL_SIZE}" fill="{color}" class="day-cell"><title>{tooltip}</title></rect>')

    # Legend - show gradient from dark to bright orange
    legend_y = height - 20
    legend_x = 40
    svg_parts.append(f'<text x="{legend_x}" y="{legend_y}" class="legend-text">Less</text>')

    # Show 5 sample cells from gradient
    for i in range(5):
        intensity = 0.2 + (i / 4) * 0.8
        r = int(CLAUDE_ORANGE_RGB[0] * intensity)
        g = int(CLAUDE_ORANGE_RGB[1] * intensity)
        b = int(CLAUDE_ORANGE_RGB[2] * intensity)
        color = f"rgb({r},{g},{b})"
        x = legend_x + 35 + (i * (CELL_SIZE + 2))
        svg_parts.append(f'<rect x="{x}" y="{legend_y - CELL_SIZE + 2}" width="{CELL_SIZE}" height="{CELL_SIZE}" fill="{color}" class="day-cell"/>')

    svg_parts.append(f'<text x="{legend_x + 35 + (5 * (CELL_SIZE + 2)) + 5}" y="{legend_y}" class="legend-text">More</text>')

    svg_parts.append('</svg>')

    return '\n'.join(svg_parts)


def _get_color(
    day_stats: DailyStats | None,
    max_tokens: int,
    date: date_type,
    today: date_type
) -> str:
    """
    Get the color for a day based on activity level using smooth gradient.

    Args:
        day_stats: Statistics for the day
        max_tokens: Maximum tokens for scaling
        date: The date of this cell
        today: Today's date

    Returns:
        RGB color string
    """
    # Future days: light grey
    if date > today:
        return CLAUDE_LIGHT_GREY

    # Past days with no activity: dark grey
    if not day_stats or day_stats.total_tokens == 0:
        return CLAUDE_DARK_GREY

    # Calculate intensity ratio (0.0 to 1.0)
    ratio = day_stats.total_tokens / max_tokens if max_tokens > 0 else 0

    # Apply non-linear scaling to make differences more visible
    ratio = ratio ** 0.5

    # True continuous gradient from dark grey to orange
    dark_grey = _hex_to_rgb(CLAUDE_DARK_GREY)
    r = int(dark_grey[0] + (CLAUDE_ORANGE_RGB[0] - dark_grey[0]) * ratio)
    g = int(dark_grey[1] + (CLAUDE_ORANGE_RGB[1] - dark_grey[1]) * ratio)
    b = int(dark_grey[2] + (CLAUDE_ORANGE_RGB[2] - dark_grey[2]) * ratio)

    return f"rgb({r},{g},{b})"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _parse_rgb(rgb_str: str) -> tuple[int, int, int]:
    """Parse 'rgb(r,g,b)' string to tuple."""
    rgb_str = rgb_str.replace('rgb(', '').replace(')', '')
    return tuple(map(int, rgb_str.split(',')))


def _generate_clawd_svg(x: int, y: int, pixel_size: int) -> str:
    """
    Generate SVG markup for the Claude guy (Clawd) pixel art icon.

    Based on ASCII art:
     ▐▛███▜▌
    ▝▜█████▛▘
      ▘▘ ▝▝

    Args:
        x: X position (left)
        y: Y position (top)
        pixel_size: Size of each pixel block

    Returns:
        SVG markup string
    """
    # Colors
    orange = f"rgb({CLAUDE_ORANGE_RGB[0]},{CLAUDE_ORANGE_RGB[1]},{CLAUDE_ORANGE_RGB[2]})"
    dark_grey = CLAUDE_DARK_GREY

    # Define the pixel grid (1 = orange, 0 = transparent, 2 = dark grey/eye)
    grid = [
        [1, 1, 1, 1, 1, 1, 1, 1],  # Row 0: top with ears
        [0, 1, 2, 1, 1, 2, 1, 0],  # Row 1: eyes row
        [0, 1, 1, 1, 1, 1, 1, 0],  # Row 2: bottom of head
        [0, 1, 1, 0, 0, 1, 1, 0],  # Row 3: legs
    ]

    svg_parts = []
    for row_idx, row in enumerate(grid):
        for col_idx, pixel_type in enumerate(row):
            if pixel_type == 0:
                continue  # Skip transparent pixels

            color = orange if pixel_type == 1 else dark_grey
            px = x + (col_idx * pixel_size)
            py = y + (row_idx * pixel_size)

            svg_parts.append(
                f'<rect x="{px}" y="{py}" width="{pixel_size}" height="{pixel_size}" fill="{color}"/>'
            )

    return '\n'.join(svg_parts)


def _draw_claude_guy(draw, x: int, y: int, pixel_size: int) -> int:
    """
    Draw the Claude guy pixel art icon.

    Based on ASCII art:
     ▐▛███▜▌
    ▝▜█████▛▘
      ▘▘ ▝▝

    Args:
        draw: PIL ImageDraw object
        x: X position (left)
        y: Y position (top)
        pixel_size: Size of each pixel block

    Returns:
        Width of the icon in pixels
    """
    # Colors
    orange = (203, 123, 93)  # CLAUDE_ORANGE_RGB
    dark_grey = (60, 60, 58)  # CLAUDE_DARK_GREY

    # Define the pixel grid (1 = orange, 0 = transparent, 2 = dark grey/eye)
    # 8 pixels wide, 4 pixels tall
    grid = [
        [1, 1, 1, 1, 1, 1, 1, 1],  # Row 0: ▐▛███▜▌ - top with ears
        [0, 1, 2, 1, 1, 2, 1, 0],  # Row 1: ▝▜█████▛▘ - eyes row
        [0, 1, 1, 1, 1, 1, 1, 0],  # Row 2: bottom of head
        [0, 1, 1, 0, 0, 1, 1, 0],  # Row 3: ▘▘ ▝▝ - legs
    ]

    # Draw each pixel
    for row_idx, row in enumerate(grid):
        for col_idx, pixel_type in enumerate(row):
            if pixel_type == 0:
                continue  # Skip transparent pixels

            color = orange if pixel_type == 1 else dark_grey
            px = x + (col_idx * pixel_size)
            py = y + (row_idx * pixel_size)

            draw.rectangle([
                px, py,
                px + pixel_size, py + pixel_size
            ], fill=color)

    return 8 * pixel_size  # Return width
#endregion
