from pathlib import Path

from picoagent.config import (
    AgentConfig,
    ChannelsConfig,
    ProvidersConfig,
    TelegramChannelConfig,
    _migrate_config,
)


# ---------------------------------------------------------------------------
# New nested-format tests
# ---------------------------------------------------------------------------

def test_new_nested_providers_config() -> None:
    """API key set in nested providers block is resolved correctly."""
    cfg = AgentConfig(
        providers=ProvidersConfig.from_dict({"groq": {"apiKey": "gsk_test_key"}}),
        agents=AgentConfig.__dataclass_fields__["agents"].default_factory(),
    )
    # Set provider explicitly
    cfg.agents = type(cfg.agents)(model="llama-3.3-70b-versatile", provider="groq")
    assert cfg.resolved_api_key() == "gsk_test_key"
    assert cfg.resolved_provider_key("groq") == "gsk_test_key"


def test_new_nested_channels_telegram() -> None:
    """Telegram config is correctly parsed from the new channels block."""
    channels = ChannelsConfig.from_dict({
        "telegram": {
            "enabled": True,
            "token": "1234567890:ABCDEF",
            "allowFrom": ["123456"],
            "replyToMessage": False,
            "pollSeconds": 5.0,
        }
    })
    tg = channels.telegram
    assert tg.enabled is True
    assert tg.token == "1234567890:ABCDEF"
    assert tg.allow_from == ["123456"]
    assert tg.reply_to_message is False
    assert tg.poll_seconds == 5.0
    assert "telegram" in channels.enabled_names


def test_channels_not_in_enabled_names_when_disabled() -> None:
    channels = ChannelsConfig.from_dict({
        "telegram": {"enabled": False, "token": "xxx"},
        "discord": {"enabled": True, "token": "yyy"},
    })
    assert "telegram" not in channels.enabled_names
    assert "discord" in channels.enabled_names


def test_new_config_roundtrip(tmp_path: Path) -> None:
    """Save and reload the new nested format correctly."""
    cfg = AgentConfig(
        providers=ProvidersConfig.from_dict({"openrouter": {"apiKey": "sk-or-test"}}),
        channels=ChannelsConfig.from_dict({
            "telegram": {"enabled": True, "token": "BOT:TOKEN", "allowFrom": ["777"]}
        }),
    )
    path = tmp_path / "config.json"
    cfg.save(path)
    loaded = AgentConfig.load(path)
    assert loaded.providers.openrouter.api_key == "sk-or-test"
    assert loaded.channels.telegram.enabled is True
    assert loaded.channels.telegram.token == "BOT:TOKEN"
    assert loaded.channels.telegram.allow_from == ["777"]


# ---------------------------------------------------------------------------
# Migration tests — old flat format → new nested structure
# ---------------------------------------------------------------------------

def test_migrate_old_flat_provider() -> None:
    """Old flat api_key + provider get migrated into providers.<name>.apiKey."""
    old = {
        "provider": "groq",
        "api_key": "gsk_old_key",
        "chat_model": "llama-3.3-70b-versatile",
    }
    migrated = _migrate_config(old)
    assert migrated["providers"]["groq"]["apiKey"] == "gsk_old_key"
    assert migrated["agents"]["model"] == "llama-3.3-70b-versatile"
    assert migrated["agents"]["provider"] == "groq"


def test_migrate_old_enabled_channels_and_tokens() -> None:
    """Old enabled_channels + channel_tokens get migrated into channels block."""
    old = {
        "enabled_channels": ["telegram"],
        "channel_tokens": {"telegram": "1234:TOKEN"},
        "channel_settings": {"telegram": {"allowed_chat_ids": ["999"]}},
    }
    migrated = _migrate_config(old)
    tg = migrated["channels"]["telegram"]
    assert tg["enabled"] is True
    assert tg["token"] == "1234:TOKEN"
    # allowed_chat_ids → allowFrom
    assert tg.get("allowFrom") == ["999"] or tg.get("allowed_chat_ids") == ["999"]


def test_migrate_old_config_loads_cleanly(tmp_path: Path) -> None:
    """Old flat config file loads without errors via AgentConfig.load()."""
    import json
    old_config = {
        "provider": "groq",
        "api_key": "gsk_migrate_test",
        "chat_model": "llama-3.3-70b-versatile",
        "embedding_model": "text-embedding-3-small",
        "enabled_channels": ["telegram"],
        "channel_tokens": {"telegram": "BOT:TOKEN"},
        "channel_settings": {},
        "whatsapp_bridge_url": "ws://127.0.0.1:3001",
        "whatsapp_bridge_token": None,
        "memory_top_k": 5,
        "memory_decay_lambda": 0.05,
        "session_memory_window": 100,
        "session_keep_recent": 25,
        "entropy_threshold_bits": 1.5,
        "shell_timeout_seconds": 20,
        "channel_poll_seconds": 3.0,
        "skill_threshold": 0.78,
        "max_active_skills": 3,
        "subagent_min_confidence": 0.8,
        "adaptive_threshold_min_bits": 0.5,
        "adaptive_threshold_max_bits": 2.5,
        "adaptive_threshold_step": 0.05,
    }
    path = tmp_path / "old_config.json"
    path.write_text(json.dumps(old_config), encoding="utf-8")
    cfg = AgentConfig.load(path)
    assert cfg.resolved_provider_key("groq") == "gsk_migrate_test"
    assert cfg.channels.telegram.enabled is True
    assert cfg.channels.telegram.token == "BOT:TOKEN"
    assert cfg.agents.provider == "groq"
    assert cfg.agents.model == "llama-3.3-70b-versatile"


# ---------------------------------------------------------------------------
# Legacy helper compat tests
# ---------------------------------------------------------------------------

def test_channel_token_compat() -> None:
    """channel_token() still works via new channels block."""
    channels = ChannelsConfig.from_dict({"slack": {"enabled": True, "token": "xoxb-slack-token"}})
    cfg = AgentConfig(channels=channels)
    assert cfg.channel_token("slack") == "xoxb-slack-token"
    assert cfg.channel_token("missing") is None


def test_enabled_channels_property() -> None:
    """enabled_channels property returns names of all enabled channels."""
    channels = ChannelsConfig.from_dict({
        "telegram": {"enabled": True, "token": "t"},
        "discord": {"enabled": False, "token": "d"},
        "slack": {"enabled": True, "token": "s"},
    })
    cfg = AgentConfig(channels=channels)
    assert "telegram" in cfg.enabled_channels
    assert "slack" in cfg.enabled_channels
    assert "discord" not in cfg.enabled_channels


def test_resolved_embedding_api_key_from_nested_providers(monkeypatch) -> None:
    providers = ProvidersConfig.from_dict({"openai": {"apiKey": "embed-key"}})
    from picoagent.config import AgentsConfig
    agents = AgentsConfig(model="gpt-4o-mini", provider="openai", embedding_provider="openai")
    cfg = AgentConfig(providers=providers, agents=agents)
    assert cfg.resolved_embedding_api_key() == "embed-key"


def test_resolved_embedding_api_key_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-embed-key")
    cfg = AgentConfig(embedding_api_key_env="OPENAI_API_KEY")
    assert cfg.resolved_embedding_api_key() == "env-embed-key"
