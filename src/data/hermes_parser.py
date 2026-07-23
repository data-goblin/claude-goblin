# region Imports
import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models.usage_record import TokenUsage, UsageRecord

# endregion


# region Functions


def _non_negative_int(value: Any) -> int:
    """Coerce a telemetry counter to a non-negative integer."""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an epoch timestamp or ISO-8601 string emitted by Hermes."""
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).astimezone()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_record(data: dict[str, Any]) -> UsageRecord | None:
    """Convert one content-free Hermes API-usage event to a UsageRecord."""
    if data.get("type") != "hermes_usage":
        return None

    session_id = str(data.get("session_id") or "").strip()
    request_id = str(data.get("api_request_id") or data.get("message_uuid") or "").strip()
    if not session_id or not request_id:
        return None

    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None

    input_tokens = _non_negative_int(usage.get("input_tokens"))
    output_tokens = _non_negative_int(usage.get("output_tokens"))
    cache_read_tokens = _non_negative_int(usage.get("cache_read_tokens"))
    cache_write_tokens = _non_negative_int(usage.get("cache_write_tokens"))
    if not any((input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)):
        return None

    timestamp = (
        _parse_timestamp(data.get("ended_at")) or _parse_timestamp(data.get("timestamp")) or datetime.now().astimezone()
    )
    provider = str(data.get("provider") or "unknown").strip() or "unknown"
    platform = str(data.get("platform") or "unknown").strip() or "unknown"
    model = data.get("response_model") or data.get("model") or "hermes-unknown"
    folder = str(data.get("cwd") or f"hermes:{platform}")
    git_branch = data.get("git_branch")

    return UsageRecord(
        timestamp=timestamp,
        session_id=session_id,
        message_uuid=request_id,
        message_type="assistant",
        model=str(model),
        folder=folder,
        git_branch=str(git_branch) if git_branch else None,
        version=f"hermes:{provider}",
        token_usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens,
        ),
    )


def parse_hermes_file(file_path: Path) -> Iterator[UsageRecord]:
    """
    Parse content-free JSONL events emitted by Hermes' post_api_request hook.

    The hook emits one event for every billed model call, including calls made
    between tool executions. Prompt, response, reasoning, tool arguments, user
    identifiers, and credentials are deliberately absent from this format.
    """
    try:
        with open(file_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(data, dict):
                    continue
                record = _parse_record(data)
                if record is not None:
                    yield record
    except (OSError, UnicodeDecodeError):
        return


def parse_all_hermes_files(file_paths: list[Path]) -> list[UsageRecord]:
    """Parse multiple Hermes telemetry JSONL files into UsageRecords."""
    records: list[UsageRecord] = []
    for path in file_paths:
        records.extend(parse_hermes_file(path))
    return records
