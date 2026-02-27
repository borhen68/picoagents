from __future__ import annotations

import asyncio
from pathlib import Path

from picoagent.agent.tools.registry import ToolContext, ToolRegistry
from picoagent.config import MCPServerConfig
from picoagent.mcp_client import close_all_mcp_sessions, register_mcp_tools_from_servers_sync


_MCP_SCRIPT = r'''
import json, sys
tool_calls = 0
while True:
    line = sys.stdin.readline()
    if not line:
        break
    line = line.strip()
    if not line:
        continue
    req = json.loads(line)
    method = req.get("method")

    # Notification (no response required)
    if "id" not in req:
        continue

    if method == "initialize":
        out = {
            "jsonrpc": "2.0",
            "id": req.get("id"),
            "result": {"serverInfo": {"name": "fake", "version": "0.1"}, "capabilities": {"tools": {}}},
        }
    elif method == "tools/list":
        out = {
            "jsonrpc": "2.0",
            "id": req.get("id"),
            "result": {
                "tools": [
                    {
                        "name": "echo",
                        "description": "echo message",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"message": {"type": "string"}},
                            "required": ["message"]
                        }
                    }
                ]
            }
        }
    elif method == "tools/call":
        tool_calls += 1
        msg = ((req.get("params") or {}).get("arguments") or {}).get("message", "")
        out = {
            "jsonrpc": "2.0",
            "id": req.get("id"),
            "result": {"content": [{"type": "text", "text": f"{msg}:{tool_calls}"}], "isError": False}
        }
    else:
        out = {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32601, "message": "Method not found"}}
    print(json.dumps(out), flush=True)
'''


def test_register_and_call_mcp_wrapped_tool() -> None:
    registry = ToolRegistry()
    server = MCPServerConfig(name="fake", command="python3", args=["-c", _MCP_SCRIPT], timeout_seconds=5)

    try:
        count = register_mcp_tools_from_servers_sync(registry, [server], workspace_root=Path("."))
        assert count == 1

        result = asyncio.run(
            registry.run(
                "mcp_fake_echo",
                {"message": "hello"},
                ToolContext(workspace_root=Path("."), session_id="t"),
            )
        )
        assert result.success is True
        assert result.output == "hello:1"

        second = asyncio.run(
            registry.run(
                "mcp_fake_echo",
                {"message": "hello"},
                ToolContext(workspace_root=Path("."), session_id="t"),
            )
        )
        assert second.success is True
        assert second.output == "hello:2"
    finally:
        close_all_mcp_sessions()
