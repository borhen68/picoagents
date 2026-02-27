from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from picoagent.agent.tools.registry import ToolContext, ToolRegistry


class MCPServer:
    """Minimal stdio JSON-RPC server for tool listing and invocation."""

    def __init__(self, tools: ToolRegistry, workspace_root: str | Path) -> None:
        self.tools = tools
        self.workspace_root = Path(workspace_root).expanduser().resolve()

    async def serve_stdio(self) -> None:
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break

            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
                self._write(response)
                continue

            response = await self._handle_request(request)
            self._write(response)

    async def _handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        try:
            if method == "initialize":
                result = {
                    "serverInfo": {"name": "picoagent", "version": "0.3.0"},
                    "capabilities": {"tools": {}},
                }
            elif method == "ping":
                result = {"ok": True}
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": name,
                            "description": desc,
                            "inputSchema": {"type": "object", "additionalProperties": True},
                        }
                        for name, desc in self.tools.docs().items()
                    ]
                }
            elif method == "tools/call":
                name = str(params.get("name", ""))
                arguments = params.get("arguments", {})
                if not isinstance(arguments, dict):
                    arguments = {}
                tool_context = ToolContext(workspace_root=self.workspace_root, session_id="mcp")
                tool_result = await self.tools.run(name, arguments, tool_context)
                result = {
                    "content": [{"type": "text", "text": tool_result.output}],
                    "isError": not tool_result.success,
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
        except Exception as exc:  # noqa: BLE001
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(exc)},
            }

        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _write(payload: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
        sys.stdout.flush()
