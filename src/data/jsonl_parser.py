#region Imports
import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from src.models.usage_record import TokenUsage, UsageRecord

#endregion


#region Functions


def parse_jsonl_file(file_path: Path) -> Iterator[UsageRecord]:
    """
    Parse a single JSONL file and yield UsageRecord objects.

    Extracts usage data from Claude Code session logs, including:
    - Token usage (input, output, cache creation, cache read)
    - Session metadata (model, folder, version, branch)
    - Timestamps and identifiers

    Args:
        file_path: Path to the JSONL file to parse

    Yields:
        UsageRecord objects for each assistant message with usage data

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                record = _parse_record(data)
                if record:
                    yield record
            except json.JSONDecodeError as e:
                # Skip malformed lines but continue processing
                print(f"Warning: Skipping malformed JSON at {file_path}:{line_num}: {e}")
                continue


def parse_all_jsonl_files(file_paths: list[Path]) -> list[UsageRecord]:
    """
    Parse multiple JSONL files and return deduplicated usage records.

    Assistant records are deduplicated GLOBALLY by their billed-response
    identity (message_uuid = API message id + request id): Claude Code
    writes one entry per streaming flush and session forks replay history
    into new session files, so one billed response can appear many times
    across entries, sessions, and files. The record with the largest total
    token usage wins (usage grows monotonically across flushes); ties keep
    the latest timestamp. User records pass through untouched.

    Args:
        file_paths: List of paths to JSONL files

    Returns:
        List of deduplicated UsageRecord objects across all files

    Raises:
        ValueError: If file_paths is empty
    """
    if not file_paths:
        raise ValueError("No JSONL files provided to parse")

    records: list[UsageRecord] = []
    for file_path in file_paths:
        try:
            records.extend(parse_jsonl_file(file_path))
        except FileNotFoundError:
            print(f"Warning: File not found, skipping: {file_path}")
        except Exception as e:
            print(f"Warning: Error parsing {file_path}: {e}")

    return dedupe_records(records)


def dedupe_records(records: list[UsageRecord]) -> list[UsageRecord]:
    """
    Collapse assistant records sharing a billed-response identity.

    Keeps, per message_uuid, the record with max total tokens (ties: latest
    timestamp), preserving first-appearance order. User records pass through.
    """
    best: dict[str, UsageRecord] = {}
    order: list[str] = []
    others: list[UsageRecord] = []
    for record in records:
        if not record.is_assistant_response:
            others.append(record)
            continue
        key = record.message_uuid
        current = best.get(key)
        if current is None:
            best[key] = record
            order.append(key)
            continue
        new_total = record.token_usage.total_tokens if record.token_usage else 0
        cur_total = current.token_usage.total_tokens if current.token_usage else 0
        if new_total > cur_total or (
            new_total == cur_total and record.timestamp > current.timestamp
        ):
            best[key] = record
    return others + [best[key] for key in order]


def _parse_record(data: dict) -> UsageRecord | None:
    """
    Parse a single JSON record into a UsageRecord.

    Processes both user prompts and assistant responses.
    Skips system events and other message types.

    Args:
        data: Parsed JSON object from JSONL line

    Returns:
        UsageRecord for user or assistant messages, None otherwise
    """
    message_type = data.get("type")

    # Only process user and assistant messages
    if message_type not in ("user", "assistant"):
        return None

    # Parse timestamp
    timestamp_str = data.get("timestamp")
    if not timestamp_str:
        return None

    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

    # Extract metadata (common to both user and assistant)
    session_id = data.get("sessionId", "unknown")
    folder = data.get("cwd", "unknown")
    git_branch = data.get("gitBranch")
    version = data.get("version", "unknown")

    # Extract message data
    message = data.get("message", {})
    model = message.get("model")

    # Identity: assistant rows key on the billed API response (message id +
    # request id) so streaming flush entries and session-fork replays of the
    # same response dedupe to one record; user/legacy rows keep the
    # transcript entry uuid.
    api_id = message.get("id")
    request_id = data.get("requestId")
    if message_type == "assistant" and api_id:
        message_uuid = f"{api_id}:{request_id}" if request_id else api_id
    else:
        message_uuid = data.get("uuid", "unknown")

    # Filter out synthetic models (test/internal artifacts)
    if model == "<synthetic>":
        return None

    # Extract content for analysis
    content = None
    char_count = 0
    if isinstance(message.get("content"), str):
        content = message["content"]
        char_count = len(content)
    elif isinstance(message.get("content"), list):
        # Handle content blocks (concatenate text)
        text_parts = []
        for block in message["content"]:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        content = "\n".join(text_parts) if text_parts else None
        char_count = len(content) if content else 0

    # Extract token usage (only available for assistant messages)
    token_usage = None
    if message_type == "assistant":
        usage_data = message.get("usage")
        if usage_data:
            cache_creation = usage_data.get("cache_creation", {})
            cache_creation_tokens = (
                cache_creation.get("cache_creation_input_tokens", 0)
                + cache_creation.get("ephemeral_5m_input_tokens", 0)
                + cache_creation.get("ephemeral_1h_input_tokens", 0)
            )

            token_usage = TokenUsage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                cache_creation_tokens=cache_creation_tokens,
                cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
                cache_creation_1h_tokens=cache_creation.get("ephemeral_1h_input_tokens", 0),
            )

    return UsageRecord(
        timestamp=timestamp,
        session_id=session_id,
        message_uuid=message_uuid,
        message_type=message_type,
        model=model,
        folder=folder,
        git_branch=git_branch,
        version=version,
        token_usage=token_usage,
        content=content,
        char_count=char_count,
    )
#endregion
