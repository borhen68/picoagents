from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BusMessage:
    session_id: str
    role: str
    content: str
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class AsyncMessageBus:
    """Merged session manager + in-memory async message bus."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[BusMessage]] = {}

    def create_session(self) -> str:
        session_id = uuid.uuid4().hex
        self._queues[session_id] = asyncio.Queue()
        return session_id

    def ensure_session(self, session_id: str) -> None:
        self._queues.setdefault(session_id, asyncio.Queue())

    async def publish(self, message: BusMessage) -> None:
        self.ensure_session(message.session_id)
        await self._queues[message.session_id].put(message)

    async def recv(self, session_id: str, timeout: float | None = None) -> BusMessage | None:
        self.ensure_session(session_id)
        queue = self._queues[session_id]
        if timeout is None:
            return await queue.get()
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    def close_session(self, session_id: str) -> None:
        self._queues.pop(session_id, None)

    def sessions(self) -> list[str]:
        return sorted(self._queues)
