import asyncio
from pathlib import Path

from picoagent.agent.tools.registry import ToolContext, ToolRegistry, ToolResult
from picoagent.mcp import MCPServer


class EchoTool:
    name = "echo"
    description = "echo a message"

    async def run(self, args, context: ToolContext):
        msg = str(args.get("message", ""))
        return ToolResult(output=msg, success=True)


def test_mcp_tools_list_and_call(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())

    server = MCPServer(tools=registry, workspace_root=tmp_path)

    list_resp = asyncio.run(server._handle_request({"id": 1, "method": "tools/list", "params": {}}))
    names = [item["name"] for item in list_resp["result"]["tools"]]
    assert "echo" in names

    call_resp = asyncio.run(
        server._handle_request(
            {
                "id": 2,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"message": "hello"}},
            }
        )
    )
    assert call_resp["result"]["content"][0]["text"] == "hello"
