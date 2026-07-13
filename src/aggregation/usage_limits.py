#region Imports
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.models.usage_record import UsageRecord

#endregion


#region Constants
# Known token limits per 5-hour session (from community research)
SESSION_LIMITS = {
    "pro": 44_000,
    "max_5x": 88_000,
    "max_20x": 220_000,
}

# Weekly limits (estimated based on usage data)
# These are approximate - Claude doesn't publish exact limits
WEEKLY_LIMITS = {
    "pro": {
        "total": 300_000,  # Rough estimate for total weekly tokens
        "opus": 0,  # Pro doesn't get Opus access
    },
    "max_5x": {
        "total": 1_500_000,  # Rough estimate
        "opus": 150_000,  # Switches at 20% usage
    },
    "max_20x": {
        "total": 3_000_000,  # Rough estimate
        "opus": 300_000,  # Switches at 50% usage
    },
}
#endregion


#region Data Classes


@dataclass
class SessionUsage:
    """Usage data for a single 5-hour session."""
    session_id: str
    start_time: datetime
    end_time: datetime
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    records: list[UsageRecord]


@dataclass
class WeeklyUsage:
    """Usage data for a week (7 days)."""
    start_date: datetime
    end_date: datetime
    total_tokens: int
    opus_tokens: int
    sonnet_tokens: int
    haiku_tokens: int
    sessions: list[SessionUsage]


@dataclass
class UsageLimits:
    """Usage limits and current usage percentages."""
    plan_type: str

    # Current session (5-hour window)
    current_session_tokens: int
    session_limit: int
    session_percentage: float
    session_reset_time: datetime | None

    # Current week (7 days)
    current_week_tokens: int
    week_limit: int
    week_percentage: float
    week_reset_time: datetime | None

    # Opus-specific (for Max plans)
    current_week_opus_tokens: int
    opus_limit: int
    opus_percentage: float
#endregion


#region Functions


def get_current_session_usage(
    records: list[UsageRecord],
    session_window_hours: int = 5
) -> tuple[int, datetime | None]:
    """
    Calculate token usage for the current 5-hour session window.

    Claude's usage limits are based on rolling 5-hour windows. A session starts
    with the first message and expires 5 hours later.

    Args:
        records: List of usage records
        session_window_hours: Hours in the session window (default: 5)

    Returns:
        Tuple of (total_tokens, session_reset_time)

    Common failure modes:
        - Empty records list returns (0, None)
        - Records without timestamps are skipped
    """
    if not records:
        return 0, None

    # Sort records by timestamp (most recent first)
    sorted_records = sorted(
        records,
        key=lambda r: r.timestamp,
        reverse=True
    )

    # Find the most recent session
    now = datetime.now(timezone.utc)
    session_window = timedelta(hours=session_window_hours)

    # The current session started with the most recent message
    most_recent = sorted_records[0]
    session_start = most_recent.timestamp
    session_end = session_start + session_window

    # Calculate tokens used in this session window
    total_tokens = 0
    for record in sorted_records:
        # Ensure timezone-aware comparison
        record_time = record.timestamp
        if record_time.tzinfo is None:
            record_time = record_time.replace(tzinfo=timezone.utc)

        # Only count records within the current session window
        if session_start <= record_time <= now:
            if record.token_usage:
                total_tokens += record.token_usage.total_tokens
        else:
            # Records are sorted, so we can break early
            break

    return total_tokens, session_end


def get_weekly_usage(
    records: list[UsageRecord],
    weeks_back: int = 0
) -> WeeklyUsage:
    """
    Calculate token usage for the current or past week.

    Args:
        records: List of usage records
        weeks_back: Number of weeks to look back (0 = current week)

    Returns:
        WeeklyUsage object with token totals by model

    Common failure modes:
        - Empty records list returns WeeklyUsage with all zeros
        - Records without token_usage are skipped
    """
    now = datetime.now(timezone.utc)

    # Calculate week boundaries
    # Week starts on Monday (isoweekday() returns 1 for Monday)
    days_since_monday = now.isoweekday() - 1
    week_start = (now - timedelta(days=days_since_monday + (weeks_back * 7))).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_end = week_start + timedelta(days=7)

    # Filter records within the week
    total_tokens = 0
    opus_tokens = 0
    sonnet_tokens = 0
    haiku_tokens = 0

    for record in records:
        # Ensure timezone-aware comparison
        record_time = record.timestamp
        if record_time.tzinfo is None:
            record_time = record_time.replace(tzinfo=timezone.utc)

        if week_start <= record_time < week_end:
            if record.token_usage:
                tokens = record.token_usage.total_tokens
                total_tokens += tokens

                # Categorize by model
                if record.model and "opus" in record.model.lower():
                    opus_tokens += tokens
                elif record.model and "sonnet" in record.model.lower():
                    sonnet_tokens += tokens
                elif record.model and "haiku" in record.model.lower():
                    haiku_tokens += tokens

    return WeeklyUsage(
        start_date=week_start,
        end_date=week_end,
        total_tokens=total_tokens,
        opus_tokens=opus_tokens,
        sonnet_tokens=sonnet_tokens,
        haiku_tokens=haiku_tokens,
        sessions=[],
    )


def calculate_usage_limits(
    records: list[UsageRecord],
    plan_type: str = "max_20x"
) -> UsageLimits:
    """
    Calculate usage limits and percentages for the current session and week.

    This function provides the same percentage calculations that Claude's /usage
    command shows, based on known plan limits.

    Args:
        records: List of usage records
        plan_type: One of "pro", "max_5x", "max_20x"

    Returns:
        UsageLimits object with current usage and percentages

    Common failure modes:
        - Invalid plan_type defaults to "max_20x"
        - Empty records list returns all zeros
    """
    if plan_type not in SESSION_LIMITS:
        plan_type = "max_20x"

    # Get session usage
    session_tokens, session_reset = get_current_session_usage(records)
    session_limit = SESSION_LIMITS[plan_type]
    session_percentage = (session_tokens / session_limit * 100) if session_limit > 0 else 0.0

    # Get weekly usage
    weekly = get_weekly_usage(records)
    week_limit = WEEKLY_LIMITS[plan_type]["total"]
    week_percentage = (weekly.total_tokens / week_limit * 100) if week_limit > 0 else 0.0

    # Get Opus-specific usage
    opus_limit = WEEKLY_LIMITS[plan_type]["opus"]
    opus_percentage = (weekly.opus_tokens / opus_limit * 100) if opus_limit > 0 else 0.0

    # Calculate week reset time (next Monday at 00:00)
    now = datetime.now(timezone.utc)
    days_until_monday = (7 - now.isoweekday() + 1) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    week_reset = (now + timedelta(days=days_until_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    return UsageLimits(
        plan_type=plan_type,
        current_session_tokens=session_tokens,
        session_limit=session_limit,
        session_percentage=session_percentage,
        session_reset_time=session_reset,
        current_week_tokens=weekly.total_tokens,
        week_limit=week_limit,
        week_percentage=week_percentage,
        week_reset_time=week_reset,
        current_week_opus_tokens=weekly.opus_tokens,
        opus_limit=opus_limit,
        opus_percentage=opus_percentage,
    )


#endregion
