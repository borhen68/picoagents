from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable


class HeartbeatRunner:
    """Periodically emits instructions from HEARTBEAT.md."""

    def __init__(self, file_path: str | Path, interval_seconds: int = 300) -> None:
        self.file_path = Path(file_path).expanduser()
        self.interval_seconds = interval_seconds

    def read_message(self) -> str:
        if not self.file_path.exists():
            return ""
        return self.file_path.read_text(encoding="utf-8").strip()

    async def run_forever(
        self,
        callback: Callable[[str], Awaitable[None]],
        *,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        stop = stop_event or asyncio.Event()
        while not stop.is_set():
            message = self.read_message()
            if message:
                await callback(message)
            await asyncio.sleep(self.interval_seconds)
