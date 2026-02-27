from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any


from picoagent.channels import (
    CLIChannel,
    DiscordChannel,
    EmailChannel,
    SlackChannel,
    TelegramChannel,
    WhatsAppChannel,
)
from picoagent.config import AgentConfig, DEFAULT_CONFIG_PATH


def build_tool_registry(config: AgentConfig) -> ToolRegistry:
    from picoagent.agent.tools import FileTool, SearchTool, ShellTool, ToolRegistry
    from picoagent.mcp_client import register_mcp_tools_from_servers_sync

    registry = ToolRegistry()
    if config.allow_shell:
        registry.register(
            ShellTool(
                default_timeout=config.shell_timeout_seconds,
                restrict_to_workspace=config.restrict_to_workspace,
                path_append=config.shell_path_append,
            )
        )
    if config.allow_web_search:
        registry.register(SearchTool())
    if config.allow_file_tool:
        registry.register(FileTool(restrict_to_workspace=config.restrict_to_workspace))
    if config.mcp_servers:
        register_mcp_tools_from_servers_sync(registry, config.mcp_servers, config.workspace_root)
    return registry


def build_markdown_skill_library(config: AgentConfig):
    from picoagent.skills import MarkdownSkillLibrary
    from picoagent.templates import TemplateLoader

    if not config.enable_skills:
        return None

    base = Path(config.workspace_root).expanduser().resolve()
    raw = Path(config.skills_path).expanduser()
    skills_dir = raw if raw.is_absolute() else (base / raw)
    return MarkdownSkillLibrary(skills_dir)


def build_agent_loop(config: AgentConfig) -> AgentLoop:
    from picoagent.agent.context import ContextBuilder
    from picoagent.agent.loop import AgentLoop
    from picoagent.agent.subagents import SubagentCoordinator
    from picoagent.core import AdaptiveThreshold, EntropyScheduler, VectorMemory
    from picoagent.core.dual_memory import DualMemoryStore
    from picoagent.providers import ProviderRegistry
    from picoagent.session import SessionManager
    from picoagent.templates import TemplateLoader

    provider = ProviderRegistry().create_client(config)
    memory = VectorMemory(decay_lambda=config.memory_decay_lambda, persistence_path=config.memory_path)
    scheduler = EntropyScheduler(threshold_bits=config.entropy_threshold_bits)
    tools = build_tool_registry(config)
    skills = build_markdown_skill_library(config)
    
    loader = TemplateLoader(workspace_root=Path(config.workspace_root), templates_dir_name=config.templates_path)
    
    dual_memory = None
    if config.dual_memory_enabled:
        dual_memory = DualMemoryStore(workspace=Path(config.workspace_root), memory_dir_name=config.dual_memory_dir)
        
    context_builder = ContextBuilder(template_loader=loader, dual_memory=dual_memory)
    
    subagents = SubagentCoordinator(provider, min_confidence=config.subagent_min_confidence) if config.enable_subagents else None
    sessions = SessionManager(config.session_store_path)
    adaptive = (
        AdaptiveThreshold(
            path=config.adaptive_threshold_path,
            initial_threshold=config.entropy_threshold_bits,
            min_threshold=config.adaptive_threshold_min_bits,
            max_threshold=config.adaptive_threshold_max_bits,
            step=config.adaptive_threshold_step,
        )
        if config.adaptive_threshold_enabled
        else None
    )
    loop = AgentLoop(
        config=config,
        provider=provider,
        memory=memory,
        scheduler=scheduler,
        tools=tools,
        context_builder=context_builder,
        skill_library=skills,
        subagent_coordinator=subagents,
        adaptive_threshold=adaptive,
        session_manager=sessions,
        dual_memory=dual_memory,
    )
    loop.load_memory()
    return loop


async def run_cli_agent(config: AgentConfig) -> None:
    loop = build_agent_loop(config)
    channel = CLIChannel()

    async def handler(user_message: str) -> str:
        turn = await loop.run_turn(user_message, session_id="cli")
        return turn.text

    await channel.start(handler)


async def run_gateway(config: AgentConfig) -> None:
    loop = build_agent_loop(config)

    async def handler(user_message: str) -> str:
        turn = await loop.run_turn(user_message)
        return turn.text

    adapters = []

    # CLI channel
    if "cli" in (config.channels.enabled_names or []):
        adapters.append(CLIChannel())

    # Telegram
    tg = config.channels.telegram
    if tg.enabled:
        adapters.append(
            TelegramChannel(
                token=tg.token or os.getenv("TELEGRAM_BOT_TOKEN"),
                poll_seconds=tg.poll_seconds,
                allowed_chat_ids=set(tg.allow_from) if tg.allow_from else None,
                reply_to_message=tg.reply_to_message,
            )
        )

    # Discord
    dc = config.channels.discord
    if dc.enabled:
        adapters.append(
            DiscordChannel(
                token=dc.token or os.getenv("DISCORD_BOT_TOKEN"),
                channel_id=dc.channel_id or None,
                poll_seconds=dc.poll_seconds,
                reply_as_reply=dc.reply_as_reply,
            )
        )

    # Slack
    sl = config.channels.slack
    if sl.enabled:
        adapters.append(
            SlackChannel(
                token=sl.token or os.getenv("SLACK_BOT_TOKEN"),
                channel_id=sl.channel_id or None,
                poll_seconds=sl.poll_seconds,
                reply_in_thread=sl.reply_in_thread,
            )
        )

    # WhatsApp
    wa = config.channels.whatsapp
    if wa.enabled:
        inbox_default = str(Path.home() / ".picoagent" / "whatsapp_inbox.jsonl")
        adapters.append(
            WhatsAppChannel(
                access_token=os.getenv("WHATSAPP_ACCESS_TOKEN"),
                phone_number_id=None,
                inbox_path=inbox_default,
                outbox_path=None,
                cursor_path=None,
                bridge_url=wa.bridge_url,
                bridge_token=wa.bridge_token or None,
                poll_seconds=wa.poll_seconds,
            )
        )

    # Email
    em = config.channels.email
    if em.enabled:
        adapters.append(
            EmailChannel(
                username=em.username or None,
                password=em.password or None,
                imap_host=em.imap_host or None,
                smtp_host=em.smtp_host or None,
                from_address=em.from_address or None,
                imap_port=em.imap_port,
                smtp_port=em.smtp_port,
                folder=em.folder,
                poll_seconds=em.poll_seconds,
                use_tls=em.use_tls,
                use_ssl=em.use_ssl,
            )
        )

    if not adapters:
        raise RuntimeError(
            "No channels enabled. Set 'enabled: true' under the channel in config.json.\n"
            "Example: {\"channels\": {\"telegram\": {\"enabled\": true, \"token\": \"YOUR_TOKEN\"}}}"
        )

    tasks = [asyncio.create_task(adapter.start(handler)) for adapter in adapters]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

    for task in done:
        exc = task.exception()
        if exc:
            for pending_task in pending:
                pending_task.cancel()
            raise exc


def cmd_onboard(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser()
    cfg = AgentConfig.load(config_path) if config_path.exists() else AgentConfig()

    if args.provider:
        cfg.provider = args.provider
    if args.base_url:
        cfg.base_url = args.base_url
    if args.chat_model:
        cfg.chat_model = args.chat_model
    if args.embedding_model:
        cfg.embedding_model = args.embedding_model
    if args.embedding_provider:
        cfg.embedding_provider = args.embedding_provider
    if args.embedding_base_url:
        cfg.embedding_base_url = args.embedding_base_url
    if args.embedding_api_key:
        cfg.embedding_api_key = args.embedding_api_key
    if args.embedding_api_key_env:
        cfg.embedding_api_key_env = args.embedding_api_key_env
    if args.api_key:
        cfg.api_key = args.api_key
    if args.workspace_root:
        cfg.workspace_root = str(Path(args.workspace_root).expanduser().resolve())
    if args.channels:
        cfg.enabled_channels = args.channels

    cfg.validate()
    cfg.ensure_runtime_dirs()
    path = cfg.save(config_path)

    heartbeat_path = Path(cfg.heartbeat_file).expanduser()
    if not heartbeat_path.exists():
        heartbeat_path.write_text("# HEARTBEAT\n\n- Keep project dependencies healthy.\n", encoding="utf-8")

    cron_path = Path(cfg.cron_file).expanduser()
    if not cron_path.exists():
        cron_path.write_text(json.dumps({"tasks": []}, indent=2), encoding="utf-8")

    skills_dir = Path(cfg.skills_path).expanduser()
    if not skills_dir.is_absolute():
        skills_dir = Path(cfg.workspace_root).expanduser().resolve() / skills_dir
    skills_dir.mkdir(parents=True, exist_ok=True)
    readme = skills_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Skills\n\nCreate nanobot-style skills here: `skills/<name>/SKILL.md`.\n",
            encoding="utf-8",
        )
        
    templates_dir = Path(cfg.templates_path).expanduser()
    if not templates_dir.is_absolute():
        templates_dir = Path(cfg.workspace_root).expanduser().resolve() / templates_dir
    templates_dir.mkdir(parents=True, exist_ok=True)
    
    soul_md = templates_dir / "SOUL.md"
    if not soul_md.exists():
        soul_md.write_text("# Soul\n\nI am picoagent, a helpful personal assistant.\n", encoding="utf-8")
        
    user_md = templates_dir / "USER.md"
    if not user_md.exists():
        user_md.write_text("# User Profile\n\nEdit this file to customize your agent's behavior.\n", encoding="utf-8")
        
    agents_md = templates_dir / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text("# Agent Instructions\n\nPlace any global instructions or rules for the agent here.\n", encoding="utf-8")

    print(f"Saved config to {path}")
    print("Set your provider API key in config.api_key or via config.api_key_env.")
    print("Configure channel_settings for telegram/discord/slack/whatsapp/email in the config JSON before running gateway.")
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    cfg = AgentConfig.load(args.config)
    asyncio.run(run_cli_agent(cfg))
    return 0


def cmd_gateway(args: argparse.Namespace) -> int:
    cfg = AgentConfig.load(args.config)
    asyncio.run(run_gateway(cfg))
    return 0


def cmd_providers(_: argparse.Namespace) -> int:
    from picoagent.providers import ProviderRegistry

    registry = ProviderRegistry()
    for spec in registry.list_specs():
        print(f"- {spec.name}: {spec.base_url} | chat={spec.default_chat_model} | emb={spec.default_embedding_model}")
    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    cfg = AgentConfig.load(args.config)
    registry = build_tool_registry(cfg)
    for name, doc in registry.docs().items():
        print(f"- {name}: {doc}")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    from picoagent.mcp import MCPServer

    cfg = AgentConfig.load(args.config)
    tools = build_tool_registry(cfg)
    server = MCPServer(tools=tools, workspace_root=cfg.workspace_root)
    asyncio.run(server.serve_stdio())
    return 0


def cmd_import_skills(args: argparse.Namespace) -> int:
    cfg = AgentConfig.load(args.config)
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        raise RuntimeError(f"source directory does not exist: {source}")

    skills_dir = Path(cfg.skills_path).expanduser()
    if not skills_dir.is_absolute():
        skills_dir = Path(cfg.workspace_root).expanduser().resolve() / skills_dir
    skills_dir.mkdir(parents=True, exist_ok=True)

    imported = 0
    for skill_md in sorted(source.glob("*/SKILL.md")):
        name = skill_md.parent.name
        target_dir = skills_dir / name
        if target_dir.exists():
            target_dir = skills_dir / f"nanobot-{name}"
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_md, target_dir / "SKILL.md")
        imported += 1

    print(f"Imported {imported} skills into {skills_dir}")
    return 0


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _as_str_set(value: Any) -> set[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
        clean = {item for item in items if item}
        return clean or None
    if isinstance(value, (list, tuple, set)):
        clean = {str(item).strip() for item in value if str(item).strip()}
        return clean or None
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="picoagent", description="Minimal async agent runtime")
    parser.set_defaults(func=lambda _: parser.print_help() or 0)

    onboard = parser.add_subparsers(dest="command")

    p_onboard = onboard.add_parser("onboard", help="Create or update config")
    p_onboard.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config file")
    p_onboard.add_argument("--provider")
    p_onboard.add_argument("--base-url")
    p_onboard.add_argument("--chat-model")
    p_onboard.add_argument("--embedding-model")
    p_onboard.add_argument("--embedding-provider", help="Optional separate provider for embeddings")
    p_onboard.add_argument("--embedding-base-url", help="Optional override base URL for embedding provider")
    p_onboard.add_argument("--embedding-api-key")
    p_onboard.add_argument("--embedding-api-key-env")
    p_onboard.add_argument("--api-key")
    p_onboard.add_argument("--workspace-root")
    p_onboard.add_argument("--channels", nargs="+", help="Enabled channels (cli telegram discord slack whatsapp email)")
    p_onboard.set_defaults(func=cmd_onboard)

    p_agent = onboard.add_parser("agent", help="Start interactive CLI agent")
    p_agent.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config file")
    p_agent.set_defaults(func=cmd_agent)

    p_gateway = onboard.add_parser("gateway", help="Start enabled channels")
    p_gateway.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config file")
    p_gateway.set_defaults(func=cmd_gateway)

    p_providers = onboard.add_parser("providers", help="List providers")
    p_providers.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config file")
    p_providers.set_defaults(func=cmd_providers)

    p_tools = onboard.add_parser("tools", help="List enabled tools")
    p_tools.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config file")
    p_tools.set_defaults(func=cmd_tools)

    p_mcp = onboard.add_parser("mcp", help="Run MCP stdio server")
    p_mcp.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config file")
    p_mcp.set_defaults(func=cmd_mcp)

    p_import_skills = onboard.add_parser("import-skills", help="Import nanobot-style SKILL.md folders")
    p_import_skills.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config file")
    p_import_skills.add_argument(
        "--source",
        required=True,
        help="Directory containing skill folders (each folder has SKILL.md)",
    )
    p_import_skills.set_defaults(func=cmd_import_skills)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
