#region Imports
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from src.models.usage_record import TokenUsage, UsageRecord

#endregion


#region Functions


def _parse_ts(value: str | None) -> datetime | None:
    """Parse a Codex ISO-8601 timestamp (trailing Z) into a datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_codex_file(file_path: Path) -> Iterator[UsageRecord]:
    """
    Parse a single Codex rollout JSONL file into UsageRecord objects.

    Codex writes one rollout file per session under ~/.codex/sessions. Each
    assistant turn emits an `event_msg`/`token_count` line carrying a
    `last_token_usage` delta (the tokens billed for that turn). We map one
    UsageRecord per turn:
      - input_tokens      = last.input_tokens - last.cached_input_tokens (uncached)
      - cache_read_tokens = last.cached_input_tokens
      - cache_creation    = 0 (Codex has no separate cache-write meter)
      - output_tokens     = last.output_tokens (already includes reasoning tokens)

    session_id is the file stem (unique per file, so resumed sessions can't
    collide) and message_uuid is the session id plus a per-file turn counter:
    globally unique so the cross-session assistant dedupe never collapses
    turns from different sessions, while re-ingestion of an appended file
    stays idempotent against the (session_id, message_uuid) key.

    Args:
        file_path: Path to a Codex rollout .jsonl file

    Yields:
        UsageRecord objects, one per billed assistant turn
    """
    import json

    session_id = file_path.stem
    model: str | None = None
    cwd = "unknown"
    version = "codex"
    turn = 0

    try:
        with open(file_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                rec_type = obj.get("type")
                payload = obj.get("payload") or {}

                if rec_type == "session_meta":
                    cwd = payload.get("cwd", cwd)
                    version = payload.get("cli_version", version)
                    continue

                if rec_type == "turn_context":
                    model = payload.get("model") or model
                    cwd = payload.get("cwd", cwd)
                    continue

                if rec_type != "event_msg" or payload.get("type") != "token_count":
                    continue

                info = payload.get("info") or {}
                last = info.get("last_token_usage") or {}
                total_in = int(last.get("input_tokens", 0) or 0)
                cached_in = int(last.get("cached_input_tokens", 0) or 0)
                out = int(last.get("output_tokens", 0) or 0)
                uncached_in = max(total_in - cached_in, 0)

                if uncached_in == 0 and cached_in == 0 and out == 0:
                    continue

                turn += 1
                ts = _parse_ts(obj.get("timestamp")) or datetime.now().astimezone()

                yield UsageRecord(
                    timestamp=ts,
                    session_id=session_id,
                    message_uuid=f"{session_id}:t{turn}",
                    message_type="assistant",
                    model=model or "codex-unknown",
                    folder=cwd,
                    git_branch=None,
                    version=version,
                    token_usage=TokenUsage(
                        input_tokens=uncached_in,
                        output_tokens=out,
                        cache_creation_tokens=0,
                        cache_read_tokens=cached_in,
                    ),
                )
    except (OSError, UnicodeDecodeError):
        return


def parse_all_codex_files(file_paths: list[Path]) -> list[UsageRecord]:
    """
    Parse multiple Codex rollout files into a flat UsageRecord list.

    Args:
        file_paths: Codex rollout .jsonl paths

    Returns:
        All UsageRecord objects found across the files
    """
    records: list[UsageRecord] = []
    for path in file_paths:
        records.extend(parse_codex_file(path))
    return records


#endregion
