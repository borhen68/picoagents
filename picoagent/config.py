from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".picoagent"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.json"
DEFAULT_MEMORY_PATH = CONFIG_DIR / "memory.npz"
DEFAULT_CRON_PATH = CONFIG_DIR / "cron.json"
DEFAULT_HEARTBEAT_PATH = CONFIG_DIR / "HEARTBEAT.md"
DEFAULT_THRESHOLD_PATH = CONFIG_DIR / "threshold.json"
DEFAULT_SESSION_PATH = CONFIG_DIR / "sessions.json"
SUPPORTED_CHANNELS = {"cli", "telegram", "discord", "slack", "whatsapp", "email"}


@dataclass(slots=True)
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPServerConfig":
        return cls(
            name=str(data.get("name", "")).strip(),
            command=str(data.get("command", "")).strip(),
            args=[str(x) for x in data.get("args", [])],
            env={str(k): str(v) for k, v in dict(data.get("env", {})).items()},
            timeout_seconds=int(data.get("timeout_seconds", 30)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "args": list(self.args),
            "env": dict(self.env),
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(slots=True)
class AgentConfig:
    provider: str = "openrouter"
    base_url: str | None = None
    chat_model: str = "openai/gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_provider: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_api_key_env: str | None = None
    api_key: str | None = None
    api_key_env: str = "PICOAGENT_API_KEY"

    entropy_threshold_bits: float = 1.5
    memory_top_k: int = 5
    memory_decay_lambda: float = 0.05
    memory_path: str = str(DEFAULT_MEMORY_PATH)
    session_store_path: str = str(DEFAULT_SESSION_PATH)
    session_memory_window: int = 100
    session_keep_recent: int = 25
    session_consolidation_enabled: bool = True
    adaptive_threshold_enabled: bool = True
    adaptive_threshold_path: str = str(DEFAULT_THRESHOLD_PATH)
    adaptive_threshold_min_bits: float = 0.5
    adaptive_threshold_max_bits: float = 2.5
    adaptive_threshold_step: float = 0.05

    enable_skills: bool = True
    skills_path: str = "skills"
    max_active_skills: int = 3
    skill_threshold: float = 0.78
    enable_subagents: bool = True
    subagent_min_confidence: float = 0.8

    allow_shell: bool = True
    allow_web_search: bool = True
    allow_file_tool: bool = True
    shell_timeout_seconds: int = 20
    workspace_root: str = str(Path.cwd())
    templates_path: str = "templates"
    restrict_to_workspace: bool = True
    shell_path_append: str = ""
    
    dual_memory_enabled: bool = True
    dual_memory_dir: str = ".picoagent/memory"

    enabled_channels: list[str] = field(default_factory=lambda: ["cli"])
    channel_tokens: dict[str, str] = field(default_factory=dict)
    channel_settings: dict[str, dict[str, Any]] = field(default_factory=dict)
    channel_poll_seconds: float = 3.0

    whatsapp_bridge_url: str | None = "ws://127.0.0.1:3001"
    whatsapp_bridge_token: str | None = None

    cron_file: str = str(DEFAULT_CRON_PATH)
    heartbeat_file: str = str(DEFAULT_HEARTBEAT_PATH)
    mcp_servers: list[MCPServerConfig] = field(default_factory=list)

    def resolved_api_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        return os.getenv(self.api_key_env)

    def resolved_embedding_api_key(self) -> str | None:
        if self.embedding_api_key:
            return self.embedding_api_key
        if self.embedding_api_key_env:
            return os.getenv(self.embedding_api_key_env)
        return None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mcp_servers"] = [server.to_dict() for server in self.mcp_servers]
        return payload

    def channel_token(self, name: str, *, env_var: str | None = None) -> str | None:
        direct = self.channel_tokens.get(name)
        if direct:
            return direct
        if env_var:
            return os.getenv(env_var)
        return None

    def channel_config(self, name: str) -> dict[str, Any]:
        return dict(self.channel_settings.get(name, {}))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        data_copy = dict(data)
        mcp_raw = data_copy.pop("mcp_servers", [])
        obj = cls(**data_copy)
        obj.mcp_servers = [MCPServerConfig.from_dict(item) for item in mcp_raw if isinstance(item, dict)]
        obj.validate()
        return obj

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "AgentConfig":
        config_path = Path(path).expanduser()
        if not config_path.exists():
            cfg = cls()
            cfg.ensure_runtime_dirs()
            return cfg

        raw = json.loads(config_path.read_text(encoding="utf-8"))
        cfg = cls.from_dict(raw)
        cfg.ensure_runtime_dirs()
        return cfg

    def save(self, path: str | Path = DEFAULT_CONFIG_PATH) -> Path:
        config_path = Path(path).expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return config_path

    def ensure_runtime_dirs(self) -> None:
        Path(self.memory_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(self.session_store_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(self.cron_file).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(self.heartbeat_file).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(self.adaptive_threshold_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        if self.memory_top_k <= 0:
            raise ValueError("memory_top_k must be > 0")
        if self.memory_decay_lambda < 0:
            raise ValueError("memory_decay_lambda must be >= 0")
        if self.session_memory_window <= 0:
            raise ValueError("session_memory_window must be > 0")
        if self.session_keep_recent <= 0:
            raise ValueError("session_keep_recent must be > 0")
        if self.session_keep_recent >= self.session_memory_window:
            raise ValueError("session_keep_recent must be < session_memory_window")
        if self.entropy_threshold_bits < 0:
            raise ValueError("entropy_threshold_bits must be >= 0")
        if self.shell_timeout_seconds <= 0:
            raise ValueError("shell_timeout_seconds must be > 0")
        if self.channel_poll_seconds <= 0:
            raise ValueError("channel_poll_seconds must be > 0")
        if not (0 <= self.skill_threshold <= 1):
            raise ValueError("skill_threshold must be between 0 and 1")
        if self.max_active_skills <= 0:
            raise ValueError("max_active_skills must be > 0")
        if not (0 <= self.subagent_min_confidence <= 1):
            raise ValueError("subagent_min_confidence must be between 0 and 1")
        if self.adaptive_threshold_min_bits < 0:
            raise ValueError("adaptive_threshold_min_bits must be >= 0")
        if self.adaptive_threshold_max_bits <= self.adaptive_threshold_min_bits:
            raise ValueError("adaptive_threshold_max_bits must be > adaptive_threshold_min_bits")
        if self.adaptive_threshold_step <= 0:
            raise ValueError("adaptive_threshold_step must be > 0")
        for server in self.mcp_servers:
            if not server.name:
                raise ValueError("mcp server name is required")
            if not server.command:
                raise ValueError(f"mcp server '{server.name}' missing command")
            if server.timeout_seconds <= 0:
                raise ValueError(f"mcp server '{server.name}' timeout_seconds must be > 0")
        invalid_channels = [name for name in self.enabled_channels if name.lower() not in SUPPORTED_CHANNELS]
        if invalid_channels:
            supported = ", ".join(sorted(SUPPORTED_CHANNELS))
            raise ValueError(f"unsupported channels: {invalid_channels}. supported channels: {supported}")
        if not self.provider:
            raise ValueError("provider is required")
        if not self.chat_model:
            raise ValueError("chat_model is required")
        if not self.embedding_model:
            raise ValueError("embedding_model is required")
        if self.embedding_provider is not None and not str(self.embedding_provider).strip():
            raise ValueError("embedding_provider cannot be empty when set")
