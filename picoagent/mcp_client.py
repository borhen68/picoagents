from __future__ import annotations

import atexit
import asyncio
import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from picoagent.agent.tools.registry import ToolContext, ToolRegistry, ToolResult
from picoagent.config import MCPServerConfig


@dataclass(slots=True)
class MCPClientTool:
    """Tool wrapper that forwards calls to a persistent external MCP session."""

    session: "MCPServerSession"
    server_name: str
    tool_name: str
    description: str
    input_schema: dict[str, Any]
    cacheable: bool = False  # MCP tools are stateful; disable TTL caching

    @property
    def name(self) -> str:
        return f"mcp_{self.server_name}_{self.tool_name}"

    @property
    def parameters(self) -> dict[str, Any]:
        schema = dict(self.input_schema or {})
        if schema.get("type") != "object":
            schema = {"type": "object", "additionalProperties": True}
        return schema

    async def run(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            result = await asyncio.to_thread(self.session.call_tool, self.tool_name, args)
        except TimeoutError:
            return ToolResult(output=f"mcp call timed out after {self.session.timeout_seconds}s", success=False)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(output=f"mcp call failed: {exc}", success=False)

        contents = result.get("content", []) if isinstance(result, dict) else []
        parts: list[str] = []
        for item in contents:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))

        output = "\n".join(part for part in parts if part).strip() or "(no output)"
        success = not bool(result.get("isError", False)) if isinstance(result, dict) else True
        return ToolResult(output=output, success=success)


class MCPServerSession:
    """Persistent JSON-RPC stdio session for a configured MCP server."""

    def __init__(self, server: MCPServerConfig, workspace_root: Path) -> None:
        self.server = server
        self.workspace_root = workspace_root
        self.timeout_seconds = server.timeout_seconds

        self._proc: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._request_lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._next_id = 1
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._closed = False
        self._stderr_tail: list[str] = []

    def start(self) -> None:
        with self._start_lock:
            if self._closed:
                raise RuntimeError(f"mcp session '{self.server.name}' is closed")
            if self.is_running:
                return

            env = {**os.environ, **dict(self.server.env)} if self.server.env else dict(os.environ)
            self._proc = subprocess.Popen(
                [self.server.command, *self.server.args],
                cwd=str(self.workspace_root),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            self._responses = queue.Queue()
            self._reader_thread = threading.Thread(target=self._reader_loop, name=f"mcp-reader-{self.server.name}", daemon=True)
            self._reader_thread.start()

            self._stderr_tail = []
            self._stderr_thread = threading.Thread(target=self._stderr_loop, name=f"mcp-stderr-{self.server.name}", daemon=True)
            self._stderr_thread.start()

            self._initialize_session()

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def close(self) -> None:
        self._closed = True
        proc = self._proc
        if proc is None:
            return

        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass

        self._proc = None

    def list_tools(self) -> list[dict[str, Any]]:
        response = self._request("tools/list", {}, timeout=self.timeout_seconds)
        if "error" in response:
            raise RuntimeError(f"mcp list tools error: {response['error']}")

        result = response.get("result", {})
        tools = result.get("tools", []) if isinstance(result, dict) else []
        return [item for item in tools if isinstance(item, dict)]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self._request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
            timeout=self.timeout_seconds,
        )
        if "error" in response:
            raise RuntimeError(str(response["error"]))
        result = response.get("result")
        return result if isinstance(result, dict) else {}

    def _initialize_session(self) -> None:
        payload = {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "picoagent", "version": "0.2.0"},
            "capabilities": {"tools": {}},
        }
        try:
            response = self._request("initialize", payload, timeout=self.timeout_seconds, start_if_needed=False)
            if "error" in response:
                return
            self._notify("notifications/initialized", {})
        except Exception:
            return

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            return
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        proc.stdin.write(json.dumps(payload, ensure_ascii=True) + "\n")
        proc.stdin.flush()

    def _request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout: int,
        start_if_needed: bool = True,
    ) -> dict[str, Any]:
        if start_if_needed:
            self.start()

        with self._request_lock:
            proc = self._proc
            if proc is None or proc.stdin is None:
                raise RuntimeError("mcp process not started")
            if proc.poll() is not None:
                raise RuntimeError("mcp process exited")

            request_id = self._next_id
            self._next_id += 1

            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }

            proc.stdin.write(json.dumps(payload, ensure_ascii=True) + "\n")
            proc.stdin.flush()

            deadline = time.time() + timeout
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError(f"timeout waiting for MCP response to method '{method}'")

                try:
                    message = self._responses.get(timeout=remaining)
                except queue.Empty as exc:
                    raise TimeoutError(f"timeout waiting for MCP response to method '{method}'") from exc

                msg_id = message.get("id")
                if msg_id == request_id:
                    return message

    def _reader_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return

        try:
            for line in proc.stdout:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    self._responses.put(payload)
        except Exception:
            return

    def _stderr_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return

        try:
            for line in proc.stderr:
                stripped = line.rstrip("\n")
                if not stripped:
                    continue
                self._stderr_tail.append(stripped)
                if len(self._stderr_tail) > 20:
                    self._stderr_tail = self._stderr_tail[-20:]
        except Exception:
            return


_SESSIONS: dict[str, MCPServerSession] = {}
_SESSIONS_LOCK = threading.Lock()


def register_mcp_tools_from_servers_sync(
    registry: ToolRegistry,
    servers: list[MCPServerConfig],
    workspace_root: str | Path,
) -> int:
    count = 0
    root = Path(workspace_root).expanduser().resolve()

    for server in servers:
        session = _get_or_create_session(server, root)
        try:
            tools = session.list_tools()
        except Exception:
            continue

        for tool_def in tools:
            name = str(tool_def.get("name", "")).strip()
            if not name:
                continue
            description = str(tool_def.get("description", name))
            input_schema = tool_def.get("inputSchema", {"type": "object", "additionalProperties": True})

            wrapped = MCPClientTool(
                session=session,
                server_name=server.name,
                tool_name=name,
                description=description,
                input_schema=input_schema if isinstance(input_schema, dict) else {"type": "object", "additionalProperties": True},
            )
            registry.register(wrapped)
            count += 1

    return count


def close_all_mcp_sessions() -> None:
    with _SESSIONS_LOCK:
        sessions = list(_SESSIONS.values())
        _SESSIONS.clear()

    for session in sessions:
        session.close()


def _session_key(server: MCPServerConfig, workspace_root: Path) -> str:
    args = "\u241f".join(server.args)
    return f"{workspace_root}::{server.name}::{server.command}::{args}"


def _get_or_create_session(server: MCPServerConfig, workspace_root: Path) -> MCPServerSession:
    key = _session_key(server, workspace_root)
    with _SESSIONS_LOCK:
        existing = _SESSIONS.get(key)
        if existing is not None and existing.is_running:
            return existing

        session = MCPServerSession(server=server, workspace_root=workspace_root)
        _SESSIONS[key] = session
        return session


atexit.register(close_all_mcp_sessions)
