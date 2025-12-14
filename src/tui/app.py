"""
Main Textual app for Claude Goblin TUI.

A warm, data-observatory style interface for viewing usage statistics
and managing Claude Code utilities.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
    from textual.widgets import Header, Footer, Static, Label, Button, DataTable, ProgressBar
    from textual.reactive import reactive

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

if TYPE_CHECKING:
    from textual.app import App


# Color scheme matching dashboard.py
AMBER = "#ffaa00"
EMBER = "#ff6600"
SAGE = "#88aa77"
SLATE = "#667788"


CSS = """
Screen {
    background: #1a1a1e;
}

#header-title {
    dock: top;
    height: 3;
    background: #252528;
    color: #ffaa00;
    text-align: center;
    padding: 1;
}

#main-content {
    layout: grid;
    grid-size: 2 2;
    grid-gutter: 1;
    padding: 1;
}

.stat-card {
    background: #252528;
    border: solid #444;
    padding: 1;
    height: 100%;
}

.stat-card-title {
    color: #888;
    text-style: bold;
}

.stat-card-value {
    color: #ffaa00;
    text-style: bold;
    text-align: center;
}

#kpi-row {
    height: 7;
    layout: horizontal;
}

.kpi-card {
    background: #252528;
    border: solid #444;
    padding: 1;
    width: 1fr;
    margin: 0 1;
}

.kpi-value {
    color: #ffaa00;
    text-style: bold;
    text-align: center;
}

.kpi-label {
    color: #666;
    text-align: center;
}

#model-table {
    background: #252528;
    border: solid #444;
    height: 100%;
}

#activity-panel {
    background: #252528;
    border: solid #444;
    height: 100%;
    padding: 1;
}

.heatmap-row {
    height: 1;
}

.heat-0 { color: #333; }
.heat-1 { color: #442200; }
.heat-2 { color: #774400; }
.heat-3 { color: #aa6600; }
.heat-4 { color: #ffaa00; }

#footer-bar {
    dock: bottom;
    height: 1;
    background: #252528;
    color: #666;
}

#menu-container {
    align: center middle;
    padding: 2;
}

.menu-button {
    width: 40;
    margin: 1;
}

#stats-panel {
    background: #252528;
    border: solid #444;
    padding: 1;
}
"""


def _fmt(num: int) -> str:
    """Format number with K/M/B suffix."""
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)


# Only define Textual widgets if textual is available
if TEXTUAL_AVAILABLE:
    class KPICard(Static):
        """A single KPI metric card."""

        def __init__(self, label: str, value: str, **kwargs) -> None:
            super().__init__(**kwargs)
            self.label = label
            self._value_text = value
            self._label_text = label

        def compose(self) -> ComposeResult:
            yield Label(self._value_text, classes="kpi-value", id="value-label")
            yield Label(self._label_text, classes="kpi-label")

        def update_value(self, new_value: str) -> None:
            """Update the displayed value."""
            self._value_text = new_value
            try:
                self.query_one("#value-label", Label).update(new_value)
            except Exception:
                pass


    class ClaudeGoblinApp(App):
        """Main TUI application for Claude Goblin."""

        TITLE = "Claude Goblin"
        SUB_TITLE = "Usage Analytics"
        CSS = CSS

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("r", "refresh", "Refresh"),
            Binding("d", "dashboard", "Dashboard"),
            Binding("?", "help", "Help"),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.stats: dict = {}
            self.records: list = []

        def compose(self) -> ComposeResult:
            yield Header()

            with Container(id="main-content"):
                # KPI Cards row
                with Horizontal(id="kpi-row"):
                    yield KPICard("Total Tokens", "...", id="kpi-tokens", classes="kpi-card")
                    yield KPICard("Prompts", "...", id="kpi-prompts", classes="kpi-card")
                    yield KPICard("Sessions", "...", id="kpi-sessions", classes="kpi-card")
                    yield KPICard("Active Days", "...", id="kpi-days", classes="kpi-card")

                # Activity heatmap
                with ScrollableContainer(id="activity-panel"):
                    yield Static("Loading activity data...", id="activity-content")

                # Model breakdown
                yield DataTable(id="model-table")

                # Stats panel
                with ScrollableContainer(id="stats-panel"):
                    yield Static("Loading statistics...", id="stats-content")

            yield Footer()

        def on_mount(self) -> None:
            """Load data when app starts."""
            self.load_data()

        def load_data(self) -> None:
            """Load usage data from database."""
            try:
                from src.storage.snapshot_db import get_database_stats, load_historical_records

                self.stats = get_database_stats()
                self.records = load_historical_records()

                self.update_kpis()
                self.update_activity()
                self.update_models()
                self.update_stats()

            except Exception as e:
                self.notify(f"Error loading data: {e}", severity="error")

        def update_kpis(self) -> None:
            """Update KPI cards with current data."""
            tokens = self.stats.get("total_tokens", 0)
            prompts = self.stats.get("total_prompts", 0)
            sessions = self.stats.get("total_sessions", 0)
            days = self.stats.get("total_days", 0)

            self.query_one("#kpi-tokens", KPICard).update_value(_fmt(tokens))
            self.query_one("#kpi-prompts", KPICard).update_value(str(prompts))
            self.query_one("#kpi-sessions", KPICard).update_value(str(sessions))
            self.query_one("#kpi-days", KPICard).update_value(str(days))

        def update_activity(self) -> None:
            """Update activity heatmap."""
            content = self.query_one("#activity-content", Static)

            if not self.records:
                content.update("No activity data available")
                return

            # Build simple text-based heatmap
            from collections import defaultdict
            from datetime import timedelta

            daily_tokens: dict[str, int] = defaultdict(int)
            for record in self.records:
                if record.token_usage:
                    daily_tokens[record.date_key] += record.token_usage.total_tokens

            if not daily_tokens:
                content.update("No token data available")
                return

            today = datetime.now().date()
            max_tokens = max(daily_tokens.values())

            # Build last 12 weeks
            lines = []
            lines.append("Activity Heatmap (last 12 weeks)")
            lines.append("")

            heat_chars = [".", ":", "*", "#", "@"]

            for week_offset in range(12, -1, -1):
                week_start = today - timedelta(days=today.weekday() + 7 * week_offset)
                week_line = ""
                for day in range(7):
                    date = week_start + timedelta(days=day)
                    date_key = date.strftime("%Y-%m-%d")
                    tokens = daily_tokens.get(date_key, 0)

                    if tokens == 0:
                        week_line += "."
                    else:
                        ratio = (tokens / max_tokens) ** 0.5
                        level = min(4, int(ratio * 5))
                        week_line += heat_chars[level]

                lines.append(week_line)

            lines.append("")
            lines.append("Legend: . (none) : * # @ (most)")

            content.update("\n".join(lines))

        def update_models(self) -> None:
            """Update model breakdown table."""
            table = self.query_one("#model-table", DataTable)
            table.clear(columns=True)
            table.add_columns("Model", "Tokens", "%")

            tokens_by_model = self.stats.get("tokens_by_model", {})
            total = sum(tokens_by_model.values())

            for model, tokens in sorted(tokens_by_model.items(), key=lambda x: -x[1]):
                name = model.replace("claude-", "").split("-20")[0]
                pct = (tokens / total * 100) if total > 0 else 0
                table.add_row(name, _fmt(tokens), f"{pct:.1f}%")

        def update_stats(self) -> None:
            """Update stats panel."""
            content = self.query_one("#stats-content", Static)

            lines = []
            lines.append("Statistics")
            lines.append("")

            total_cost = self.stats.get("total_cost", 0)
            avg_per_session = self.stats.get("avg_tokens_per_session", 0)
            avg_per_response = self.stats.get("avg_tokens_per_response", 0)

            lines.append(f"API Cost Equivalent: ${total_cost:.2f}")
            lines.append(f"Avg Tokens/Session: {_fmt(avg_per_session)}")
            lines.append(f"Avg Tokens/Response: {_fmt(avg_per_response)}")
            lines.append("")

            oldest = self.stats.get("oldest_date", "N/A")
            newest = self.stats.get("newest_date", "N/A")
            lines.append(f"Date Range: {oldest} to {newest}")

            content.update("\n".join(lines))

        def action_refresh(self) -> None:
            """Refresh data."""
            self.notify("Refreshing data...")
            self.load_data()
            self.notify("Data refreshed", severity="information")

        def action_dashboard(self) -> None:
            """Show dashboard view."""
            self.load_data()

        def action_help(self) -> None:
            """Show help."""
            self.notify(
                "Keys: [r] Refresh | [d] Dashboard | [q] Quit",
                severity="information"
            )

else:
    # Stubs for when textual is not available
    KPICard = None
    ClaudeGoblinApp = None


def run_tui() -> None:
    """Run the TUI application."""
    if not TEXTUAL_AVAILABLE:
        from rich.console import Console
        console = Console()
        console.print("[red]Error:[/red] Textual is not installed.")
        console.print("Install with: [cyan]pip install claude-goblin[tui][/cyan]")
        return

    app = ClaudeGoblinApp()
    app.run()


if __name__ == "__main__":
    run_tui()
