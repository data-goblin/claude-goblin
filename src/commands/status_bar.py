#region Imports
import sys
import time
import re
from typing import Literal
from rich.console import Console

try:
    import rumps
except ImportError:
    rumps = None
#endregion


#region Functions


def _strip_timezone(reset_time: str) -> str:
    """
    Remove timezone information from reset time string.

    Converts "in 2 hours (PST)" to "in 2 hours"
    Converts "Monday at 9:00 AM PST" to "Monday at 9:00 AM"

    Args:
        reset_time: Reset time string with optional timezone

    Returns:
        Reset time without timezone info
    """
    # Remove timezone in parentheses: "(PST)", "(UTC)", etc.
    result = re.sub(r'\s*\([A-Z]{2,5}\)', '', reset_time)
    # Remove trailing timezone abbreviations: "PST", "UTC", etc.
    result = re.sub(r'\s+[A-Z]{2,5}$', '', result)
    return result.strip()


def run(console: Console, limit_type: Literal["session", "weekly", "opus"]) -> None:
    """
    Launch macOS menu bar app showing Claude Code usage percentage.

    NOTE: This feature is temporarily disabled due to changes in Claude Code's
    output format. Will be re-enabled in a future release.

    Args:
        console: Rich console for output
        limit_type: Type of limit to display ("session", "weekly", or "opus")
    """
    console.print()
    console.print("[yellow]Status bar is temporarily unavailable.[/yellow]")
    console.print("[dim]Claude Code's /usage output format has changed.[/dim]")
    console.print("[dim]This feature will be restored in a future release.[/dim]")
    console.print()
    console.print("[dim]In the meantime, run 'claude /usage' directly to view your limits.[/dim]")
    console.print()
    return

    # --- DISABLED CODE BELOW ---
    # Check platform
    if sys.platform != 'darwin':
        console.print("[red]Error: --status-bar is only available on macOS[/red]")
        sys.exit(1)

    # Check if rumps is available
    if rumps is None:
        console.print("[red]Error: rumps library not installed[/red]")
        console.print("[yellow]Install with: uv pip install rumps[/yellow]")
        sys.exit(1)

    # Import the capture function from limits
    from src.commands.limits import capture_limits

    class ClaudeStatusApp(rumps.App):
        """
        macOS menu bar app for displaying Claude Code usage.

        Shows usage percentage in menu bar with format "CC: XX%"
        Updates every 5 minutes automatically.
        """

        def __init__(self, limit_type: str):
            super(ClaudeStatusApp, self).__init__("CC: --", quit_button="Quit")
            self.limit_type = limit_type
            self.update_interval = 300  # 5 minutes in seconds

            # Set up menu items - will be populated in update_usage
            self.menu_refresh = rumps.MenuItem("Refresh Now", callback=self.manual_refresh)
            self.menu_session = rumps.MenuItem("Loading...")
            self.menu_weekly = rumps.MenuItem("Loading...")
            self.menu_opus = rumps.MenuItem("Loading...")

            self.menu.add(self.menu_refresh)
            self.menu.add(rumps.separator)
            self.menu.add(self.menu_session)
            self.menu.add(self.menu_weekly)
            self.menu.add(self.menu_opus)

            # Initial update
            self.update_usage()

        @rumps.timer(300)  # Update every 5 minutes
        def update_usage(self, _: rumps.Timer | None = None) -> None:
            """
            Update the menu bar display with current usage.

            Fetches latest usage data from Claude and updates the menu bar title.
            Called automatically every 5 minutes and on manual refresh.

            Args:
                _: Timer object (unused, required by rumps.timer decorator)
            """
            limits = capture_limits()

            if limits is None:
                self.title = "CC: ??"
                self.menu_session.title = "Error: Could not fetch usage data"
                self.menu_weekly.title = ""
                self.menu_opus.title = ""
                return

            # Check for trust prompt error
            if "error" in limits:
                self.title = "CC: ??"
                self.menu_session.title = "Error: " + limits.get("message", "Unknown error")
                self.menu_weekly.title = ""
                self.menu_opus.title = ""
                return

            # Extract all three percentages and reset times
            session_pct = limits.get("session_pct", 0)
            week_pct = limits.get("week_pct", 0)
            opus_pct = limits.get("opus_pct", 0)

            session_reset = _strip_timezone(limits.get("session_reset", "Unknown"))
            week_reset = _strip_timezone(limits.get("week_reset", "Unknown"))
            opus_reset = _strip_timezone(limits.get("opus_reset", "Unknown"))

            # Update menu bar title based on selected limit type
            if self.limit_type == "session":
                pct = session_pct
            elif self.limit_type == "weekly":
                pct = week_pct
            elif self.limit_type == "opus":
                pct = opus_pct
            else:
                self.title = "CC: ??"
                self.menu_session.title = f"Error: Invalid limit type '{self.limit_type}'"
                self.menu_weekly.title = ""
                self.menu_opus.title = ""
                return

            # Update menu bar title
            self.title = f"CC: {pct}%"

            # Update all three menu items to show all limits
            self.menu_session.title = f"Session: {session_pct}% (resets {session_reset})"
            self.menu_weekly.title = f"Weekly: {week_pct}% (resets {week_reset})"
            self.menu_opus.title = f"Opus: {opus_pct}% (resets {opus_reset})"

        def manual_refresh(self, _: rumps.MenuItem) -> None:
            """
            Handle manual refresh request from menu.

            Args:
                _: Menu item that triggered the callback (unused)
            """
            self.update_usage()

    # Launch the app
    console.print(f"[green]Launching status bar app (showing {limit_type} usage)...[/green]")
    console.print("[dim]The app will appear in your menu bar as 'CC: XX%'[/dim]")
    console.print("[dim]Press Ctrl+C or select 'Quit' from the menu to stop[/dim]")

    app = ClaudeStatusApp(limit_type)
    app.run()


#endregion
