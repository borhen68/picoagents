from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from picoagent.cli import _start_cron_runner
from picoagent.config import AgentConfig


class _DummyLoop:
    def __init__(self) -> None:
        self.turns: list[tuple[str, str | None]] = []

    async def run_turn(self, user_message: str, session_id: str | None = None):
        self.turns.append((user_message, session_id))
        return None


@pytest.mark.asyncio
async def test_start_cron_runner_uses_configured_cron_file(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeCronRunner:
        def __init__(self, file_path: str | Path) -> None:
            captured["file_path"] = Path(file_path)

        async def run_forever(self, callback, *, poll_seconds: float = 2.0, stop_event=None) -> None:
            captured["poll_seconds"] = poll_seconds
            await callback(SimpleNamespace(prompt="hello world"))

    monkeypatch.setattr("picoagent.cron.CronRunner", FakeCronRunner)

    cfg = AgentConfig(
        workspace_root=str(tmp_path),
        cron_file=str(tmp_path / "isolated-cron.json"),
    )
    loop = _DummyLoop()

    task = await _start_cron_runner(cfg, loop)
    await task

    assert captured["file_path"] == (tmp_path / "isolated-cron.json")
    assert captured["poll_seconds"] == 2.0
    assert loop.turns == [("hello world", "cron")]
