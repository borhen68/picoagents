from __future__ import annotations

import json
from pathlib import Path

import pytest

from picoagent.agent.tools.cron import CronTool
from picoagent.agent.tools.registry import ToolContext


@pytest.mark.asyncio
async def test_cron_tool_writes_to_context_cron_file(tmp_path: Path) -> None:
    tool = CronTool()
    cron_file = tmp_path / "isolated-cron.json"
    context = ToolContext(workspace_root=tmp_path, session_id="test", cron_file=cron_file)

    result = await tool.run(
        {"action": "add", "message": "hello world", "every_seconds": 10},
        context,
    )

    assert result.success
    payload = json.loads(cron_file.read_text(encoding="utf-8"))
    assert len(payload["tasks"]) == 1
    assert payload["tasks"][0]["prompt"] == "hello world"
    assert payload["tasks"][0]["interval_seconds"] == 10


@pytest.mark.asyncio
async def test_cron_tool_accepts_common_interval_aliases(tmp_path: Path) -> None:
    tool = CronTool()
    cron_file = tmp_path / "isolated-cron.json"
    context = ToolContext(workspace_root=tmp_path, session_id="test", cron_file=cron_file)

    result = await tool.run(
        {"action": "add", "prompt": "Time to drink water!", "everyseconds": "7200"},
        context,
    )

    assert result.success
    payload = json.loads(cron_file.read_text(encoding="utf-8"))
    assert len(payload["tasks"]) == 1
    assert payload["tasks"][0]["prompt"] == "Time to drink water!"
    assert payload["tasks"][0]["interval_seconds"] == 7200
