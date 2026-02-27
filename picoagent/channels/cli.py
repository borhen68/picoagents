from __future__ import annotations

from typing import Awaitable, Callable


class CLIChannel:
    name = "cli"

    async def start(self, handler: Callable[[str], Awaitable[str]]) -> None:
        print("picoagent CLI started. Type 'exit' to quit.")
        while True:
            try:
                user = input("you> ").strip()
            except EOFError:
                print()
                break
            if not user:
                continue
            if user.lower() in {"exit", "quit"}:
                break
            response = await handler(user)
            print(f"agent> {response}")
