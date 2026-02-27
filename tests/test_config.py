from pathlib import Path

from picoagent.config import AgentConfig


def test_channel_config_helpers() -> None:
    cfg = AgentConfig(
        channel_tokens={"slack": "token-1"},
        channel_settings={"email": {"imap_host": "imap.example.com", "smtp_port": 465}},
    )

    assert cfg.channel_token("slack") == "token-1"
    assert cfg.channel_token("missing") is None

    email_cfg = cfg.channel_config("email")
    assert email_cfg["imap_host"] == "imap.example.com"
    assert email_cfg["smtp_port"] == 465


def test_channel_settings_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    cfg = AgentConfig(
        enabled_channels=["cli", "slack", "email"],
        channel_settings={"slack": {"channel_id": "C123"}, "email": {"imap_host": "imap.local"}},
        embedding_provider="openai",
        embedding_api_key_env="OPENAI_API_KEY",
    )
    cfg.save(path)

    loaded = AgentConfig.load(path)
    assert loaded.enabled_channels == ["cli", "slack", "email"]
    assert loaded.channel_config("slack")["channel_id"] == "C123"
    assert loaded.channel_config("email")["imap_host"] == "imap.local"
    assert loaded.embedding_provider == "openai"
    assert loaded.embedding_api_key_env == "OPENAI_API_KEY"


def test_invalid_channel_rejected() -> None:
    cfg = AgentConfig(enabled_channels=["cli", "unknown"])
    try:
        cfg.validate()
    except ValueError as exc:
        assert "unsupported channels" in str(exc)
    else:
        raise AssertionError("expected validation error for unsupported channel")


def test_resolved_embedding_api_key_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "embed-key")
    cfg = AgentConfig(embedding_api_key_env="OPENAI_API_KEY")
    assert cfg.resolved_embedding_api_key() == "embed-key"
