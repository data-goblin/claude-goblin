#region Imports
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.models.usage_record import UsageRecord

#endregion


#region Data Classes


@dataclass
class DailyStats:
    """
    Aggregated statistics for a single day.

    Attributes:
        date: Date in YYYY-MM-DD format
        total_prompts: Number of user prompts (user messages)
        total_responses: Number of assistant responses (assistant messages)
        total_sessions: Number of unique sessions
        total_tokens: Total token count across all categories
        input_tokens: Total input tokens
        output_tokens: Total output tokens
        cache_creation_tokens: Total cache creation tokens
        cache_read_tokens: Total cache read tokens
        models: Set of unique model names used
        folders: Set of unique project folders
    """

    date: str
    total_prompts: int
    total_responses: int
    total_sessions: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    models: set[str]
    folders: set[str]


@dataclass
class AggregatedStats:
    """
    Complete statistics across all time periods.

    Attributes:
        daily_stats: Dictionary mapping date strings to DailyStats
        overall_totals: DailyStats object with totals across all dates
    """

    daily_stats: dict[str, DailyStats]
    overall_totals: DailyStats
#endregion


#region Functions


def aggregate_by_day(records: list[UsageRecord]) -> dict[str, DailyStats]:
    """
    Aggregate usage records by day.

    Groups records by date and calculates totals for each metric.

    Args:
        records: List of usage records to aggregate

    Returns:
        Dictionary mapping date strings (YYYY-MM-DD) to DailyStats objects

    Raises:
        ValueError: If records list is empty
    """
    if not records:
        return {}

    # Group records by date
    daily_data: defaultdict[str, list[UsageRecord]] = defaultdict(list)
    for record in records:
        daily_data[record.date_key].append(record)

    # Aggregate statistics for each day
    daily_stats: dict[str, DailyStats] = {}
    for date, day_records in daily_data.items():
        daily_stats[date] = _calculate_day_stats(date, day_records)

    return daily_stats


def calculate_overall_stats(records: list[UsageRecord]) -> DailyStats:
    """
    Calculate overall statistics across all records.

    Args:
        records: List of all usage records

    Returns:
        DailyStats object with totals across all time periods
    """
    if not records:
        return DailyStats(
            date="all",
            total_prompts=0,
            total_responses=0,
            total_sessions=0,
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            models=set(),
            folders=set(),
        )

    return _calculate_day_stats("all", records)


def aggregate_all(records: list[UsageRecord]) -> AggregatedStats:
    """
    Create complete aggregated statistics from usage records.

    Args:
        records: List of all usage records

    Returns:
        AggregatedStats object with daily and overall totals
    """
    return AggregatedStats(
        daily_stats=aggregate_by_day(records),
        overall_totals=calculate_overall_stats(records),
    )


def get_date_range(daily_stats: dict[str, DailyStats], days: int = 365) -> list[str]:
    """
    Get a list of dates for the specified range, ending today.

    Creates a continuous date range even if some days have no data.

    Args:
        daily_stats: Dictionary of daily statistics (used to determine if we have any data)
        days: Number of days to include in range (default: 365)

    Returns:
        List of date strings in YYYY-MM-DD format, from oldest to newest
    """
    if not daily_stats:
        # If no data, return empty range
        return []

    today = datetime.now().date()
    start_date = today - timedelta(days=days - 1)

    date_range = []
    current_date = start_date
    while current_date <= today:
        date_range.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)

    return date_range


def _calculate_day_stats(date: str, records: list[UsageRecord]) -> DailyStats:
    """
    Calculate statistics for a single day's records.

    Args:
        date: Date string in YYYY-MM-DD format
        records: All usage records for this day

    Returns:
        DailyStats object with aggregated metrics
    """
    unique_sessions = set()
    models = set()
    folders = set()

    total_prompts = 0
    total_responses = 0
    total_tokens = 0
    input_tokens = 0
    output_tokens = 0
    cache_creation_tokens = 0
    cache_read_tokens = 0

    for record in records:
        unique_sessions.add(record.session_id)
        if record.model:
            models.add(record.model)
        folders.add(record.folder)

        # Count message types separately
        if record.is_user_prompt:
            total_prompts += 1
        elif record.is_assistant_response:
            total_responses += 1

        # Token usage only available on assistant responses
        if record.token_usage:
            total_tokens += record.token_usage.total_tokens
            input_tokens += record.token_usage.input_tokens
            output_tokens += record.token_usage.output_tokens
            cache_creation_tokens += record.token_usage.cache_creation_tokens
            cache_read_tokens += record.token_usage.cache_read_tokens

    return DailyStats(
        date=date,
        total_prompts=total_prompts,
        total_responses=total_responses,
        total_sessions=len(unique_sessions),
        total_tokens=total_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
        models=models,
        folders=folders,
    )
#endregion
