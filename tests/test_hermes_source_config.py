from src.config import user_config


def test_get_extra_sources_accepts_hermes(monkeypatch) -> None:
    monkeypatch.setattr(
        user_config,
        "load_config",
        lambda: {
            "extra_sources": [
                {
                    "path": "/var/lib/ccg/hermes-usage",
                    "device_id": "hermes-agent-host",
                    "device_name": "Hermes Agent (host)",
                    "device_type": "linux",
                    "format": "hermes",
                }
            ]
        },
    )

    sources = user_config.get_extra_sources()

    assert len(sources) == 1
    assert sources[0]["format"] == "hermes"


def test_get_extra_sources_falls_back_for_unknown_format(monkeypatch) -> None:
    monkeypatch.setattr(
        user_config,
        "load_config",
        lambda: {
            "extra_sources": [
                {
                    "path": "/tmp/source",
                    "device_id": "device-1",
                    "device_name": "Device 1",
                    "device_type": "linux",
                    "format": "not-real",
                }
            ]
        },
    )

    assert user_config.get_extra_sources()[0]["format"] == "claude"
