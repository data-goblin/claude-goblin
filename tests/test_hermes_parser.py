import json
from pathlib import Path

from src.data.hermes_parser import parse_all_hermes_files, parse_hermes_file


def _write(path: Path, rows: list[object]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_parses_one_usage_record_into_existing_schema(tmp_path: Path) -> None:
    path = tmp_path / "usage.jsonl"
    _write(
        path,
        [
            {
                "type": "hermes_usage",
                "ended_at": 1_753_200_000.5,
                "session_id": "session-1",
                "api_request_id": "turn-1:api:2",
                "platform": "telegram",
                "provider": "local-cluster",
                "model": "minimax-m2.7",
                "response_model": "minimax-m2.7",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_tokens": 70,
                    "cache_write_tokens": 10,
                    "reasoning_tokens": 5,
                },
            }
        ],
    )

    records = list(parse_hermes_file(path))

    assert len(records) == 1
    record = records[0]
    assert record.session_id == "session-1"
    assert record.message_uuid == "turn-1:api:2"
    assert record.message_type == "assistant"
    assert record.model == "minimax-m2.7"
    assert record.folder == "hermes:telegram"
    assert record.version == "hermes:local-cluster"
    assert record.token_usage is not None
    assert record.token_usage.input_tokens == 100
    assert record.token_usage.output_tokens == 20
    assert record.token_usage.cache_read_tokens == 70
    assert record.token_usage.cache_creation_tokens == 10
    assert record.token_usage.total_tokens == 200


def test_skips_content_non_usage_and_malformed_rows(tmp_path: Path) -> None:
    path = tmp_path / "usage.jsonl"
    path.write_text(
        "not-json\n"
        + json.dumps({"type": "hermes_usage", "session_id": "missing-request", "usage": {}})
        + "\n"
        + json.dumps({"type": "some_other_event", "content": "do not ingest"})
        + "\n",
        encoding="utf-8",
    )

    assert list(parse_hermes_file(path)) == []


def test_clamps_bad_counters_and_uses_optional_metadata(tmp_path: Path) -> None:
    path = tmp_path / "usage.jsonl"
    _write(
        path,
        [
            {
                "type": "hermes_usage",
                "timestamp": "2026-07-23T10:00:00Z",
                "session_id": "session-2",
                "message_uuid": "request-2",
                "platform": "cron",
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "cwd": "/work/world",
                "git_branch": "main",
                "usage": {
                    "input_tokens": -12,
                    "output_tokens": "9",
                    "cache_read_tokens": "bad",
                    "cache_write_tokens": 3,
                },
            }
        ],
    )

    record = list(parse_hermes_file(path))[0]
    assert record.folder == "/work/world"
    assert record.git_branch == "main"
    assert record.version == "hermes:anthropic"
    assert record.token_usage is not None
    assert record.token_usage.input_tokens == 0
    assert record.token_usage.output_tokens == 9
    assert record.token_usage.cache_read_tokens == 0
    assert record.token_usage.cache_creation_tokens == 3


def test_parse_all_files(tmp_path: Path) -> None:
    paths = [tmp_path / "a.jsonl", tmp_path / "b.jsonl"]
    for index, path in enumerate(paths):
        _write(
            path,
            [
                {
                    "type": "hermes_usage",
                    "session_id": f"session-{index}",
                    "api_request_id": f"request-{index}",
                    "usage": {"output_tokens": 1},
                }
            ],
        )

    assert len(parse_all_hermes_files(paths)) == 2
