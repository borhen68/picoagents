import pytest
from pathlib import Path
from picoagent.agent.tools.registry import ToolContext
from picoagent.agent.tools.file import FileTool


@pytest.mark.asyncio
async def test_file_tool_sandbox_blocks_external_read(tmp_path: Path):
    context = ToolContext(workspace_root=tmp_path / "workspace", session_id="test")
    context.workspace_root.mkdir()
    
    # Create a secret file OUTSIDE the workspace
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("passwords")

    tool = FileTool(restrict_to_workspace=True)

    # Attempt path traversal read
    result = await tool.run({"action": "read", "path": "../secret.txt"}, context)
    assert not result.success
    assert "escapes workspace root" in result.output

    # Attempt absolute path read
    result2 = await tool.run({"action": "read", "path": str(secret_file)}, context)
    assert not result2.success
    assert "escapes workspace root" in result2.output


@pytest.mark.asyncio
async def test_file_tool_sandbox_allows_internal_read(tmp_path: Path):
    context = ToolContext(workspace_root=tmp_path / "workspace", session_id="test")
    context.workspace_root.mkdir()
    
    # Create a safe file INSIDE the workspace
    safe_file = context.workspace_root / "safe.txt"
    safe_file.write_text("hello")

    tool = FileTool(restrict_to_workspace=True)

    for path_arg in ["safe.txt", "./safe.txt", str(safe_file)]:
        result = await tool.run({"action": "read", "path": path_arg}, context)
        assert result.success
        assert result.output == "hello"


@pytest.mark.asyncio
async def test_file_tool_no_sandbox_allows_external_read(tmp_path: Path):
    context = ToolContext(workspace_root=tmp_path / "workspace", session_id="test")
    context.workspace_root.mkdir()
    
    # Create a secret file OUTSIDE the workspace
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("passwords")

    # Disable sandboxing
    tool = FileTool(restrict_to_workspace=False)

    # Should succeed now
    result = await tool.run({"action": "read", "path": "../secret.txt"}, context)
    assert result.success
    assert result.output == "passwords"
