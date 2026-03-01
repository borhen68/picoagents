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


# ---------------------------------------------------------------------------
# MCP
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Providers — nested block: { "providers": { "groq": { "apiKey": "..." } } }
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ProviderConfig:
    """Per-provider credentials."""
    api_key: str = ""
    base_url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderConfig":
        return cls(
            api_key=str(data.get("apiKey") or data.get("api_key") or "").strip(),
            base_url=data.get("apiBase") or data.get("base_url") or None,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"apiKey": self.api_key}
        if self.base_url:
            out["apiBase"] = self.base_url
        return out


@dataclass(slots=True)
class ProvidersConfig:
    """Holds credentials for every supported provider."""
    openrouter: ProviderConfig = field(default_factory=ProviderConfig)
    anthropic: ProviderConfig = field(default_factory=ProviderConfig)
    openai: ProviderConfig = field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = field(default_factory=ProviderConfig)
    groq: ProviderConfig = field(default_factory=ProviderConfig)
    gemini: ProviderConfig = field(default_factory=ProviderConfig)
    vllm: ProviderConfig = field(default_factory=ProviderConfig)
    custom: ProviderConfig = field(default_factory=ProviderConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProvidersConfig":
        def _load(name: str) -> ProviderConfig:
            raw = data.get(name, {})
            return ProviderConfig.from_dict(raw) if isinstance(raw, dict) else ProviderConfig()
        return cls(
            openrouter=_load("openrouter"),
            anthropic=_load("anthropic"),
            openai=_load("openai"),
            deepseek=_load("deepseek"),
            groq=_load("groq"),
            gemini=_load("gemini"),
            vllm=_load("vllm"),
            custom=_load("custom"),
        )

    def get(self, name: str) -> ProviderConfig | None:
        return getattr(self, name, None)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in ("openrouter", "anthropic", "openai", "deepseek", "groq", "gemini", "vllm", "custom"):
            cfg: ProviderConfig = getattr(self, name)
            if cfg.api_key or cfg.base_url:
                out[name] = cfg.to_dict()
        return out


# ---------------------------------------------------------------------------
# Agents — nested block: { "agents": { "model": "...", "provider": "..." } }
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AgentsConfig:
    """Top-level agent defaults (model selection)."""
    model: str = "openai/gpt-4o-mini"
    provider: str = "auto"
    embedding_model: str = "text-embedding-3-small"
    embedding_provider: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentsConfig":
        return cls(
            model=str(data.get("model") or "openai/gpt-4o-mini"),
            provider=str(data.get("provider") or "auto"),
            embedding_model=str(data.get("embeddingModel") or data.get("embedding_model") or "text-embedding-3-small"),
            embedding_provider=data.get("embeddingProvider") or data.get("embedding_provider") or None,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"model": self.model, "provider": self.provider}
        if self.embedding_model != "text-embedding-3-small":
            out["embeddingModel"] = self.embedding_model
        if self.embedding_provider:
            out["embeddingProvider"] = self.embedding_provider
        return out


# ---------------------------------------------------------------------------
# Channels — one typed config per channel
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TelegramChannelConfig:
    enabled: bool = False
    token: str = ""
    allow_from: list[str] = field(default_factory=list)   # allowed chat IDs
    reply_to_message: bool = True
    poll_seconds: float = 3.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TelegramChannelConfig":
        return cls(
            enabled=bool(data.get("enabled", False)),
            token=str(data.get("token") or "").strip(),
            allow_from=[str(x) for x in (data.get("allowFrom") or data.get("allow_from") or [])],
            reply_to_message=bool(data.get("replyToMessage", data.get("reply_to_message", True))),
            poll_seconds=float(data.get("pollSeconds", data.get("poll_seconds", 3.0))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "token": self.token,
            "allowFrom": self.allow_from,
            "replyToMessage": self.reply_to_message,
            "pollSeconds": self.poll_seconds,
        }


@dataclass(slots=True)
class DiscordChannelConfig:
    enabled: bool = False
    token: str = ""
    channel_id: str = ""
    allow_from: list[str] = field(default_factory=list)
    reply_as_reply: bool = True
    poll_seconds: float = 3.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DiscordChannelConfig":
        return cls(
            enabled=bool(data.get("enabled", False)),
            token=str(data.get("token") or "").strip(),
            channel_id=str(data.get("channelId") or data.get("channel_id") or "").strip(),
            allow_from=[str(x) for x in (data.get("allowFrom") or data.get("allow_from") or [])],
            reply_as_reply=bool(data.get("replyAsReply", data.get("reply_as_reply", True))),
            poll_seconds=float(data.get("pollSeconds", data.get("poll_seconds", 3.0))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "token": self.token,
            "channelId": self.channel_id,
            "allowFrom": self.allow_from,
            "replyAsReply": self.reply_as_reply,
            "pollSeconds": self.poll_seconds,
        }


@dataclass(slots=True)
class SlackChannelConfig:
    enabled: bool = False
    token: str = ""
    channel_id: str = ""
    reply_in_thread: bool = True
    poll_seconds: float = 3.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SlackChannelConfig":
        return cls(
            enabled=bool(data.get("enabled", False)),
            token=str(data.get("token") or "").strip(),
            channel_id=str(data.get("channelId") or data.get("channel_id") or "").strip(),
            reply_in_thread=bool(data.get("replyInThread", data.get("reply_in_thread", True))),
            poll_seconds=float(data.get("pollSeconds", data.get("poll_seconds", 3.0))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "token": self.token,
            "channelId": self.channel_id,
            "replyInThread": self.reply_in_thread,
            "pollSeconds": self.poll_seconds,
        }


@dataclass(slots=True)
class WhatsAppChannelConfig:
    enabled: bool = False
    allow_from: list[str] = field(default_factory=list)
    bridge_url: str = "ws://127.0.0.1:3001"
    bridge_token: str = ""
    poll_seconds: float = 3.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WhatsAppChannelConfig":
        return cls(
            enabled=bool(data.get("enabled", False)),
            allow_from=[str(x) for x in (data.get("allowFrom") or data.get("allow_from") or [])],
            bridge_url=str(data.get("bridgeUrl") or data.get("bridge_url") or "ws://127.0.0.1:3001"),
            bridge_token=str(data.get("bridgeToken") or data.get("bridge_token") or ""),
            poll_seconds=float(data.get("pollSeconds", data.get("poll_seconds", 3.0))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "allowFrom": self.allow_from,
            "bridgeUrl": self.bridge_url,
            "bridgeToken": self.bridge_token,
            "pollSeconds": self.poll_seconds,
        }


@dataclass(slots=True)
class EmailChannelConfig:
    enabled: bool = False
    username: str = ""
    password: str = ""
    imap_host: str = ""
    smtp_host: str = ""
    from_address: str = ""
    imap_port: int = 993
    smtp_port: int = 587
    folder: str = "INBOX"
    use_tls: bool = True
    use_ssl: bool = False
    poll_seconds: float = 30.0
    allow_from: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmailChannelConfig":
        return cls(
            enabled=bool(data.get("enabled", False)),
            username=str(data.get("username") or "").strip(),
            password=str(data.get("password") or "").strip(),
            imap_host=str(data.get("imapHost") or data.get("imap_host") or "").strip(),
            smtp_host=str(data.get("smtpHost") or data.get("smtp_host") or "").strip(),
            from_address=str(data.get("fromAddress") or data.get("from_address") or "").strip(),
            imap_port=int(data.get("imapPort", data.get("imap_port", 993))),
            smtp_port=int(data.get("smtpPort", data.get("smtp_port", 587))),
            folder=str(data.get("folder") or "INBOX"),
            use_tls=bool(data.get("useTls", data.get("use_tls", True))),
            use_ssl=bool(data.get("useSsl", data.get("use_ssl", False))),
            poll_seconds=float(data.get("pollSeconds", data.get("poll_seconds", 30.0))),
            allow_from=[str(x) for x in (data.get("allowFrom") or data.get("allow_from") or [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "username": self.username,
            "password": self.password,
            "imapHost": self.imap_host,
            "smtpHost": self.smtp_host,
            "fromAddress": self.from_address,
            "imapPort": self.imap_port,
            "smtpPort": self.smtp_port,
            "folder": self.folder,
            "useTls": self.use_tls,
            "useSsl": self.use_ssl,
            "pollSeconds": self.poll_seconds,
            "allowFrom": self.allow_from,
        }


@dataclass(slots=True)
class ChannelsConfig:
    telegram: TelegramChannelConfig = field(default_factory=TelegramChannelConfig)
    discord: DiscordChannelConfig = field(default_factory=DiscordChannelConfig)
    slack: SlackChannelConfig = field(default_factory=SlackChannelConfig)
    whatsapp: WhatsAppChannelConfig = field(default_factory=WhatsAppChannelConfig)
    email: EmailChannelConfig = field(default_factory=EmailChannelConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelsConfig":
        return cls(
            telegram=TelegramChannelConfig.from_dict(data.get("telegram") or {}),
            discord=DiscordChannelConfig.from_dict(data.get("discord") or {}),
            slack=SlackChannelConfig.from_dict(data.get("slack") or {}),
            whatsapp=WhatsAppChannelConfig.from_dict(data.get("whatsapp") or {}),
            email=EmailChannelConfig.from_dict(data.get("email") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in ("telegram", "discord", "slack", "whatsapp", "email"):
            cfg = getattr(self, name)
            if cfg.enabled:
                out[name] = cfg.to_dict()
        return out

    @property
    def enabled_names(self) -> list[str]:
        """Return names of all enabled channels."""
        names = []
        for name in ("telegram", "discord", "slack", "whatsapp", "email"):
            if getattr(self, name).enabled:
                names.append(name)
        return names


# ---------------------------------------------------------------------------
# Root AgentConfig
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AgentConfig:
    # ── New nested blocks ─────────────────────────────────────────
    providers: ProvidersConfig = field(default_factory=ProvidersConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)
    channels: ChannelsConfig = field(default_factory=ChannelsConfig)

    # ── Legacy / advanced flat fields (still supported) ──────────
    # kept for backwards compat and advanced use; prefer using nested blocks
    base_url: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_api_key_env: str | None = None
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
    tool_timeout_seconds: float = 30.0
    workspace_root: str = str(Path.cwd())
    templates_path: str = "templates"
    restrict_to_workspace: bool = True
    shell_path_append: str = ""

    dual_memory_enabled: bool = True
    dual_memory_dir: str = ".picoagent/memory"

    channel_poll_seconds: float = 3.0

    cron_file: str = str(DEFAULT_CRON_PATH)
    heartbeat_file: str = str(DEFAULT_HEARTBEAT_PATH)
    mcp_servers: list[MCPServerConfig] = field(default_factory=list)

    # ── Convenience properties (map new → old names used by registry) ──────

    @property
    def provider(self) -> str:
        """Active chat provider name. 'auto' means auto-detect from model prefix."""
        return self.agents.provider

    @property
    def chat_model(self) -> str:
        return self.agents.model

    @property
    def embedding_model(self) -> str:
        return self.agents.embedding_model

    @property
    def embedding_provider(self) -> str | None:
        return self.agents.embedding_provider

    def resolved_api_key(self) -> str | None:
        """Resolve API key: nested providers block → env var → fallback."""
        # 1. Try nested providers block
        if self.agents.provider != "auto":
            pcfg = self.providers.get(self.agents.provider)
            if pcfg and pcfg.api_key:
                return pcfg.api_key
        # 2. Fallback: try each known provider that has a key set
        for name in ("openrouter", "anthropic", "openai", "deepseek", "groq", "gemini", "vllm", "custom"):
            pcfg = self.providers.get(name)
            if pcfg and pcfg.api_key:
                return pcfg.api_key
        # 3. Env-var fallback
        return os.getenv(self.api_key_env)

    def resolved_provider_key(self, provider_name: str) -> str | None:
        """Get api key for a specific provider by name."""
        pcfg = self.providers.get(provider_name)
        if pcfg and pcfg.api_key:
            return pcfg.api_key
        return None

    def resolved_embedding_api_key(self) -> str | None:
        if self.embedding_api_key:
            return self.embedding_api_key
        emb_prov = self.agents.embedding_provider
        if emb_prov:
            pcfg = self.providers.get(emb_prov)
            if pcfg and pcfg.api_key:
                return pcfg.api_key
        if self.embedding_api_key_env:
            return os.getenv(self.embedding_api_key_env)
        return None

    # ── Legacy helpers (kept for backwards compat) ────────────────

    def channel_token(self, name: str, *, env_var: str | None = None) -> str | None:
        """Get token for a channel. Reads from new channels block."""
        ch = getattr(self.channels, name, None)
        if ch and getattr(ch, "token", None):
            return ch.token
        if env_var:
            return os.getenv(env_var)
        return None

    def channel_config(self, name: str) -> dict[str, Any]:
        """Get channel config as dict (legacy compat)."""
        ch = getattr(self.channels, name, None)
        if ch:
            return ch.to_dict()
        return {}

    @property
    def enabled_channels(self) -> list[str]:
        """Return list of enabled channel names from new nested config."""
        return self.channels.enabled_names

    # ── Serialisation ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "providers": self.providers.to_dict(),
            "agents": self.agents.to_dict(),
            "channels": self.channels.to_dict(),
            # advanced flat fields
            "base_url": self.base_url,
            "embedding_base_url": self.embedding_base_url,
            "embedding_api_key": self.embedding_api_key,
            "embedding_api_key_env": self.embedding_api_key_env,
            "api_key_env": self.api_key_env,
            "entropy_threshold_bits": self.entropy_threshold_bits,
            "memory_top_k": self.memory_top_k,
            "memory_decay_lambda": self.memory_decay_lambda,
            "memory_path": self.memory_path,
            "session_store_path": self.session_store_path,
            "session_memory_window": self.session_memory_window,
            "session_keep_recent": self.session_keep_recent,
            "session_consolidation_enabled": self.session_consolidation_enabled,
            "adaptive_threshold_enabled": self.adaptive_threshold_enabled,
            "adaptive_threshold_path": self.adaptive_threshold_path,
            "adaptive_threshold_min_bits": self.adaptive_threshold_min_bits,
            "adaptive_threshold_max_bits": self.adaptive_threshold_max_bits,
            "adaptive_threshold_step": self.adaptive_threshold_step,
            "enable_skills": self.enable_skills,
            "skills_path": self.skills_path,
            "max_active_skills": self.max_active_skills,
            "skill_threshold": self.skill_threshold,
            "enable_subagents": self.enable_subagents,
            "subagent_min_confidence": self.subagent_min_confidence,
            "allow_shell": self.allow_shell,
            "allow_web_search": self.allow_web_search,
            "allow_file_tool": self.allow_file_tool,
            "shell_timeout_seconds": self.shell_timeout_seconds,
            "tool_timeout_seconds": self.tool_timeout_seconds,
            "workspace_root": self.workspace_root,
            "templates_path": self.templates_path,
            "restrict_to_workspace": self.restrict_to_workspace,
            "shell_path_append": self.shell_path_append,
            "dual_memory_enabled": self.dual_memory_enabled,
            "dual_memory_dir": self.dual_memory_dir,
            "channel_poll_seconds": self.channel_poll_seconds,
            "cron_file": self.cron_file,
            "heartbeat_file": self.heartbeat_file,
            "mcp_servers": [s.to_dict() for s in self.mcp_servers],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        data = _migrate_config(dict(data))
        mcp_raw = data.pop("mcp_servers", [])

        providers = ProvidersConfig.from_dict(data.pop("providers", {}))
        agents = AgentsConfig.from_dict(data.pop("agents", {}))
        channels = ChannelsConfig.from_dict(data.pop("channels", {}))

        # Remove now-migrated legacy flat keys so cls() doesn't choke on unknown kwargs
        for legacy_key in (
            "provider", "api_key", "chat_model", "embedding_model",
            "embedding_provider", "enabled_channels", "channel_tokens", "channel_settings",
            "whatsapp_bridge_url", "whatsapp_bridge_token",
        ):
            data.pop(legacy_key, None)

        obj = cls(providers=providers, agents=agents, channels=channels, **data)
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
        config_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        # Restrict permissions to owner-only (0600) since config may contain API keys
        try:
            config_path.chmod(0o600)
        except OSError:
            pass  # Windows or other OS may not support chmod
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
        if not self.agents.model:
            raise ValueError("agents.model is required")
        if not self.agents.embedding_model:
            raise ValueError("agents.embedding_model is required")


# ---------------------------------------------------------------------------
# Migration — old flat keys → new nested structure
# ---------------------------------------------------------------------------

def _migrate_config(data: dict[str, Any]) -> dict[str, Any]:
    """Transparently convert flat old-style configs to the new nested format."""

    # --- Providers migration ---
    providers = dict(data.get("providers") or {})
    old_provider = str(data.get("provider") or "").strip()
    old_api_key = str(data.get("api_key") or "").strip()
    old_base_url = data.get("base_url")

    if old_api_key and old_provider and old_provider not in ("auto",):
        # Seed the specific provider block from the flat api_key
        if old_provider not in providers:
            providers[old_provider] = {}
        if not providers[old_provider].get("apiKey") and not providers[old_provider].get("api_key"):
            providers[old_provider]["apiKey"] = old_api_key
        if old_base_url and not providers[old_provider].get("apiBase") and not providers[old_provider].get("base_url"):
            providers[old_provider]["apiBase"] = old_base_url

    data["providers"] = providers

    # --- Agents migration ---
    agents = dict(data.get("agents") or {})
    if not agents.get("model"):
        old_model = str(data.get("chat_model") or "").strip()
        if old_model:
            agents["model"] = old_model
    if not agents.get("provider"):
        if old_provider:
            agents["provider"] = old_provider
    old_emb_model = str(data.get("embedding_model") or "").strip()
    if old_emb_model and not agents.get("embeddingModel") and not agents.get("embedding_model"):
        agents["embeddingModel"] = old_emb_model
    old_emb_prov = data.get("embedding_provider")
    if old_emb_prov and not agents.get("embeddingProvider") and not agents.get("embedding_provider"):
        agents["embeddingProvider"] = old_emb_prov
    data["agents"] = agents

    # --- Channels migration ---
    channels = dict(data.get("channels") or {})
    old_enabled = list(data.get("enabled_channels") or [])
    old_tokens: dict[str, str] = dict(data.get("channel_tokens") or {})
    old_settings: dict[str, dict] = dict(data.get("channel_settings") or {})

    # Also migrate flat whatsapp bridge settings
    old_wa_bridge_url = data.get("whatsapp_bridge_url")
    old_wa_bridge_token = data.get("whatsapp_bridge_token")

    for ch_name in old_enabled:
        ch_name_lower = ch_name.lower()
        if ch_name_lower == "cli":
            continue  # CLI is implicit, not in channels block
        ch_data = dict(channels.get(ch_name_lower) or {})
        ch_data.setdefault("enabled", True)

        # Merge token from channel_tokens
        token = old_tokens.get(ch_name_lower) or old_tokens.get(ch_name)
        if token and not ch_data.get("token"):
            ch_data["token"] = token

        # Merge settings from channel_settings
        settings = old_settings.get(ch_name_lower) or old_settings.get(ch_name) or {}
        for k, v in settings.items():
            if k not in ch_data:
                ch_data[k] = v

        # Migrate allowed_chat_ids → allowFrom (telegram)
        if ch_name_lower == "telegram":
            old_acl = ch_data.pop("allowed_chat_ids", None)
            if old_acl and not ch_data.get("allowFrom") and not ch_data.get("allow_from"):
                ch_data["allowFrom"] = list(old_acl) if isinstance(old_acl, (list, set)) else [str(old_acl)]

        # WhatsApp: bridge settings
        if ch_name_lower == "whatsapp":
            if old_wa_bridge_url and not ch_data.get("bridgeUrl") and not ch_data.get("bridge_url"):
                ch_data["bridgeUrl"] = old_wa_bridge_url
            if old_wa_bridge_token and not ch_data.get("bridgeToken") and not ch_data.get("bridge_token"):
                ch_data["bridgeToken"] = old_wa_bridge_token

        channels[ch_name_lower] = ch_data

    data["channels"] = channels
    return data
