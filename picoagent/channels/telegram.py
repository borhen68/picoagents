from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(slots=True)
class TelegramInbound:
    update_id: int
    chat_id: str
    message_id: int
    text: str


class TelegramChannel:
    """
    Telegram channel with typing indicator, command menu, and reply support.
    Uses long-polling (no webhook/public IP needed).
    """
    name = "telegram"

    # Bot commands registered with Telegram's command menu
    BOT_COMMANDS = [
        {"command": "start", "description": "Start the bot"},
        {"command": "new",   "description": "Start a new conversation"},
        {"command": "help",  "description": "Show available commands"},
    ]

    def __init__(
        self,
        *,
        token: str | None,
        poll_seconds: float = 3.0,
        allowed_chat_ids: set[str] | None = None,
        reply_to_message: bool = True,
        timeout_seconds: int = 25,
    ) -> None:
        self.token = token
        self.poll_seconds = poll_seconds
        self.allowed_chat_ids = allowed_chat_ids
        self.reply_to_message = reply_to_message
        self.timeout_seconds = timeout_seconds
        self._offset = 0
        self._running = False

    async def start(self, handler: Callable[[str], Awaitable[str]]) -> None:
        if not self.token:
            raise RuntimeError("telegram token not configured")

        self._running = True
        self._offset = await asyncio.to_thread(self._bootstrap_offset)

        # Register command menu with BotFather
        try:
            await asyncio.to_thread(self._set_my_commands)
        except Exception:
            pass  # non-fatal

        while self._running:
            try:
                updates = await asyncio.to_thread(self._fetch_updates, self._offset)
            except Exception:
                await asyncio.sleep(self.poll_seconds)
                continue

            inbound, next_offset = self._extract_inbound(updates, current_offset=self._offset)
            self._offset = next_offset

            for msg in inbound:
                if self.allowed_chat_ids and msg.chat_id not in self.allowed_chat_ids:
                    continue

                # Handle slash commands
                text = msg.text.strip()
                if text.startswith("/"):
                    cmd = text.split()[0].lower().lstrip("/").split("@")[0]
                    if cmd == "start":
                        await asyncio.to_thread(
                            self._send_message,
                            msg.chat_id,
                            "👋 Hi! I'm *picoagent*, your AI assistant.\n\n"
                            "Send me a message and I'll respond!\n"
                            "Use /help to see available commands.",
                            None,
                        )
                        continue
                    elif cmd == "help":
                        await asyncio.to_thread(
                            self._send_message,
                            msg.chat_id,
                            "🤖 *picoagent commands:*\n"
                            "/start — Start the bot\n"
                            "/new — Start a new conversation\n"
                            "/help — Show available commands",
                            None,
                        )
                        continue
                    elif cmd == "new":
                        await asyncio.to_thread(
                            self._send_message,
                            msg.chat_id,
                            "🔄 New conversation started. What can I help you with?",
                            None,
                        )
                        continue
                    # Unknown commands fall through to the agent

                # Start typing indicator
                typing_task = asyncio.create_task(
                    self._typing_loop(msg.chat_id)
                )

                try:
                    response = await handler(text)
                finally:
                    typing_task.cancel()
                    try:
                        await typing_task
                    except asyncio.CancelledError:
                        pass

                reply_id = msg.message_id if self.reply_to_message else None
                await asyncio.to_thread(self._send_message, msg.chat_id, response, reply_id)

            await asyncio.sleep(self.poll_seconds)

    async def _typing_loop(self, chat_id: str) -> None:
        """Repeatedly send 'typing' action until cancelled."""
        try:
            while True:
                await asyncio.to_thread(self._send_chat_action, chat_id, "typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass

    def _send_chat_action(self, chat_id: str, action: str) -> None:
        self._api_call("sendChatAction", {"chat_id": chat_id, "action": action})

    def _set_my_commands(self) -> None:
        self._api_call("setMyCommands", {"commands": self.BOT_COMMANDS})

    def _bootstrap_offset(self) -> int:
        updates = self._fetch_updates(offset=0, limit=100, timeout=0)
        if not updates:
            return 0
        last_update = max(int(item.get("update_id", 0)) for item in updates)
        return last_update + 1

    def _fetch_updates(self, offset: int, limit: int = 20, timeout: int = 20) -> list[dict[str, Any]]:
        payload = {
            "offset": offset,
            "limit": limit,
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        data = self._api_call("getUpdates", payload)
        result = data.get("result", [])
        if not isinstance(result, list):
            return []
        return [item for item in result if isinstance(item, dict)]

    def _send_message(self, chat_id: str, text: str, reply_to_message_id: int | None) -> None:
        for chunk in _split_message(text, max_len=3900):
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }
            if self.reply_to_message and reply_to_message_id is not None:
                payload["reply_to_message_id"] = reply_to_message_id

            try:
                self._api_call("sendMessage", payload)
            except RuntimeError:
                # Fallback: send as plain text if Markdown parse fails
                payload.pop("parse_mode", None)
                try:
                    self._api_call("sendMessage", payload)
                except RuntimeError:
                    pass

    def _api_call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError("telegram token not configured")

        url = f"https://api.telegram.org/bot{self.token}/{method}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"telegram HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"telegram request failed: {exc}") from exc

        parsed = json.loads(body)
        if not parsed.get("ok"):
            raise RuntimeError(f"telegram API error: {parsed}")
        return parsed

    @staticmethod
    def _extract_inbound(updates: list[dict[str, Any]], *, current_offset: int) -> tuple[list[TelegramInbound], int]:
        inbound: list[TelegramInbound] = []
        next_offset = current_offset

        for item in updates:
            update_id = int(item.get("update_id", 0))
            if update_id >= next_offset:
                next_offset = update_id + 1

            message = item.get("message")
            if not isinstance(message, dict):
                continue

            sender = message.get("from")
            if isinstance(sender, dict) and sender.get("is_bot"):
                continue

            chat = message.get("chat")
            chat_id = str((chat or {}).get("id", "")).strip()
            if not chat_id:
                continue

            text = str(message.get("text") or message.get("caption") or "").strip()
            if not text:
                continue

            message_id = int(message.get("message_id", 0))
            inbound.append(
                TelegramInbound(update_id=update_id, chat_id=chat_id, message_id=message_id, text=text)
            )

        inbound.sort(key=lambda m: m.update_id)
        return inbound, next_offset


def _split_message(content: str, max_len: int = 3900) -> list[str]:
    from picoagent.channels.utils import split_message
    return split_message(content, max_len=max_len)
