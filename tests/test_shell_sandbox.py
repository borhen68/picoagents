import pytest
from pathlib import Path
from picoagent.agent.tools.registry import ToolContext
from picoagent.agent.tools.shell import ShellTool


@pytest.mark.asyncio
async def test_shell_tool_sandbox_blocks_destuctive(tmp_path: Path):
    context = ToolContext(workspace_root=tmp_path, session_id="test")
    tool = ShellTool(restrict_to_workspace=True)

    commands_to_block = [
        "rm -rf /",
        "rm -r .",
        "del /f /s /q c:\\",
        "format C:",
        "shutdown -h now",
        ":(){ :|:& };:"
    ]

    for cmd in commands_to_block:
        result = await tool.run({"command": cmd}, context)
        assert not result.success
        assert "blocked by safety guard (dangerous pattern detected)" in result.output


@pytest.mark.asyncio
async def test_shell_tool_sandbox_blocks_path_traversal(tmp_path: Path):
    context = ToolContext(workspace_root=tmp_path, session_id="test")
    tool = ShellTool(restrict_to_workspace=True)

    traversals = [
        "cat ../../etc/passwd",
        "ls ..",
        f"ls {tmp_path.parent}",  # absolute path outside workspace
    ]

    for cmd in traversals:
        result = await tool.run({"command": cmd}, context)
        assert not result.success
        assert "blocked by safety guard" in result.output


@pytest.mark.asyncio
async def test_shell_tool_allows_safe_commands(tmp_path: Path):
    context = ToolContext(workspace_root=tmp_path, session_id="test")
    tool = ShellTool(restrict_to_workspace=True)

    # Simple echo
    result = await tool.run({"command": "echo 'hello world'"}, context)
    assert result.success
    assert result.output == "hello world"

    # Reading a file inside workspace
    safefile = tmp_path / "safe.txt"
    safefile.write_text("safe content")
    
    result2 = await tool.run({"command": f"cat {safefile}"}, context)
    assert result2.success
    assert result2.output == "safe content"

    # Absolute path but inside workspace is allowed
    result3 = await tool.run({"command": f"ls {tmp_path}"}, context)
    assert result3.success
    assert "safe.txt" in result3.output
