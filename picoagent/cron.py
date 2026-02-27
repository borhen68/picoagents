from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable


@dataclass(slots=True)
class CronTask:
    name: str
    prompt: str
    interval_seconds: int
    enabled: bool = True
    last_run: float = 0.0


@dataclass(slots=True)
class CronState:
    tasks: list[CronTask] = field(default_factory=list)


class CronRunner:
    """Simple interval-based cron runner backed by a JSON file."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path).expanduser()
        self.state = CronState()

    def load(self) -> CronState:
        if not self.file_path.exists():
            self.state = CronState()
            return self.state

        raw = json.loads(self.file_path.read_text(encoding="utf-8"))
        tasks = [CronTask(**item) for item in raw.get("tasks", [])]
        self.state = CronState(tasks=tasks)
        return self.state

    def save(self) -> Path:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tasks": [
                {
                    "name": t.name,
                    "prompt": t.prompt,
                    "interval_seconds": t.interval_seconds,
                    "enabled": t.enabled,
                    "last_run": t.last_run,
                }
                for t in self.state.tasks
            ]
        }
        self.file_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return self.file_path

    async def run_forever(
        self,
        callback: Callable[[CronTask], Awaitable[None]],
        *,
        poll_seconds: float = 2.0,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        self.load()
        stop = stop_event or asyncio.Event()

        while not stop.is_set():
            now = time.time()
            changed = False
            for task in self.state.tasks:
                if not task.enabled:
                    continue
                if now - task.last_run >= task.interval_seconds:
                    await callback(task)
                    task.last_run = now
                    changed = True
            if changed:
                self.save()
            await asyncio.sleep(poll_seconds)
