import asyncio

import numpy as np

from picoagent.agent.loop import AgentLoop
from picoagent.agent.tools.registry import ToolContext, ToolRegistry, ToolResult
from picoagent.config import AgentConfig
from picoagent.core.memory import VectorMemory
from picoagent.core.scheduler import EntropyScheduler
from picoagent.providers.registry import ProviderError
from picoagent.session import SessionManager


class DummyTool:
    name = "dummy"
    description = "Dummy tool for tests."
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict, context: ToolContext) -> ToolResult:
        return ToolResult(output="dummy-ok", success=True)


class ShellLikeTool:
    name = "shell"
    description = "Shell-like test tool."
    parameters = {
        "type": "object",
        "properties": {"command": {"type": "string", "minLength": 1}},
        "required": ["command"],
    }

    async def run(self, args: dict, context: ToolContext) -> ToolResult:
        return ToolResult(output=f"ran:{args.get('command', '')}", success=True)


class FailingScoreProvider:
    def embed(self, text: str) -> np.ndarray:
        return np.array([1.0, 0.0], dtype=np.float32)

    def score_tools(self, message: str, tool_docs: dict[str, str]) -> dict[str, float]:
        raise ProviderError("provider HTTP 403: error code: 1010")

    def plan_tool_args(self, message: str, tool_name: str, tool_doc: str) -> dict:
        return {}

    def synthesize_response(
        self,
        user_message: str,
        tool_name: str,
        tool_result: str,
        memories: list[str],
    ) -> str:
        return f"tool={tool_name} output={tool_result}"

    def chat(self, user_prompt: str, *, system_prompt: str | None = None) -> str:
        return user_prompt


class InvalidShellArgsProvider:
    def embed(self, text: str) -> np.ndarray:
        return np.array([1.0, 0.0], dtype=np.float32)

    def score_tools(self, message: str, tool_docs: dict[str, str]) -> dict[str, float]:
        return {"shell": 1.0}

    def plan_tool_args(self, message: str, tool_name: str, tool_doc: str) -> dict:
        # Simulate provider returning invalid args for shell.
        return {}

    def synthesize_response(
        self,
        user_message: str,
        tool_name: str,
        tool_result: str,
        memories: list[str],
    ) -> str:
        return tool_result

    def chat(self, user_prompt: str, *, system_prompt: str | None = None) -> str:
        return "chat-ok"


def test_agent_loop_falls_back_when_provider_scoring_fails(tmp_path) -> None:
    config = AgentConfig(
        workspace_root=str(tmp_path),
        session_store_path=str(tmp_path / "sessions.json"),
        adaptive_threshold_enabled=False,
        enable_skills=False,
        enable_subagents=False,
    )
    provider = FailingScoreProvider()
    memory = VectorMemory(decay_lambda=0.0)
    scheduler = EntropyScheduler(threshold_bits=config.entropy_threshold_bits)
    tools = ToolRegistry()
    tools.register(DummyTool())
    sessions = SessionManager(config.session_store_path)

    loop = AgentLoop(
        config=config,
        provider=provider,
        memory=memory,
        scheduler=scheduler,
        tools=tools,
        session_manager=sessions,
    )

    result = asyncio.run(loop.run_turn("read file config.json", session_id="test"))

    assert result.selected_tool == "dummy"
    assert result.text == "tool=dummy output=dummy-ok"


def test_agent_loop_repairs_missing_shell_command_args(tmp_path) -> None:
    config = AgentConfig(
        workspace_root=str(tmp_path),
        session_store_path=str(tmp_path / "sessions.json"),
        adaptive_threshold_enabled=False,
        enable_skills=False,
        enable_subagents=False,
    )
    provider = InvalidShellArgsProvider()
    memory = VectorMemory(decay_lambda=0.0)
    scheduler = EntropyScheduler(threshold_bits=config.entropy_threshold_bits)
    tools = ToolRegistry()
    tools.register(ShellLikeTool())
    sessions = SessionManager(config.session_store_path)

    loop = AgentLoop(
        config=config,
        provider=provider,
        memory=memory,
        scheduler=scheduler,
        tools=tools,
        session_manager=sessions,
    )

    result = asyncio.run(loop.run_turn("ls -la", session_id="test"))

    assert result.selected_tool == "shell"
    assert result.tool_args.get("command") == "ls -la"
    assert result.tool_output == "ran:ls -la"


def test_agent_loop_clarifies_for_non_command_shell_message(tmp_path) -> None:
    config = AgentConfig(
        workspace_root=str(tmp_path),
        session_store_path=str(tmp_path / "sessions.json"),
        adaptive_threshold_enabled=False,
        enable_skills=False,
        enable_subagents=False,
    )
    provider = InvalidShellArgsProvider()
    memory = VectorMemory(decay_lambda=0.0)
    scheduler = EntropyScheduler(threshold_bits=config.entropy_threshold_bits)
    tools = ToolRegistry()
    tools.register(ShellLikeTool())
    sessions = SessionManager(config.session_store_path)

    loop = AgentLoop(
        config=config,
        provider=provider,
        memory=memory,
        scheduler=scheduler,
        tools=tools,
        session_manager=sessions,
    )

    result = asyncio.run(loop.run_turn("hellp", session_id="test"))

    assert result.selected_tool is None
    assert result.text == "chat-ok"
