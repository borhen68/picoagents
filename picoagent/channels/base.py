from __future__ import annotations

from typing import Awaitable, Callable, Protocol


class ChannelAdapter(Protocol):
    name: str

    async def start(self, handler: Callable[[str], Awaitable[str]]) -> None:
        ...
