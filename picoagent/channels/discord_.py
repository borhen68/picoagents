from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(slots=True)
class DiscordInbound:
    message_id: str
    content: str


class DiscordChannel:
    name = "discord"

    def __init__(
        self,
        *,
        token: str | None,
        channel_id: str | None,
        poll_seconds: float = 3.0,
        reply_as_reply: bool = True,
        timeout_seconds: int = 20,
    ) -> None:
        self.token = token
        self.channel_id = channel_id
        self.poll_seconds = poll_seconds
        self.reply_as_reply = reply_as_reply
        self.timeout_seconds = timeout_seconds
        self._bot_user_id: str | None = None

    async def start(self, handler: Callable[[str], Awaitable[str]]) -> None:
        if not self.token:
            raise RuntimeError("discord token not configured")
        if not self.channel_id:
            raise RuntimeError("discord channel_id not configured")

        self._bot_user_id = await asyncio.to_thread(self._resolve_bot_user_id)
        last_message_id = await asyncio.to_thread(self._latest_message_id)

        while True:
            try:
                raw_messages = await asyncio.to_thread(self._fetch_messages, last_message_id)
            except Exception:
                await asyncio.sleep(self.poll_seconds)
                continue

            inbound, last_message_id = self._extract_inbound(
                raw_messages,
                after_id=last_message_id,
                bot_user_id=self._bot_user_id,
            )

            for msg in inbound:
                response = await handler(msg.content)
                await asyncio.to_thread(self._send_message, response, msg.message_id)

            await asyncio.sleep(self.poll_seconds)

    def _resolve_bot_user_id(self) -> str | None:
        data = self._request("GET", "/users/@me")
        user_id = str(data.get("id", "")).strip()
        return user_id or None

    def _latest_message_id(self) -> str:
        assert self.channel_id is not None
        params = urllib.parse.urlencode({"limit": 1})
        data = self._request("GET", f"/channels/{self.channel_id}/messages?{params}")
        if not isinstance(data, list) or not data:
            return "0"
        return str(data[0].get("id", "0"))

    def _fetch_messages(self, after_id: str) -> list[dict[str, Any]]:
        assert self.channel_id is not None
        params = urllib.parse.urlencode({"limit": 50, "after": after_id})
        data = self._request("GET", f"/channels/{self.channel_id}/messages?{params}")
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _send_message(self, text: str, source_message_id: str | None) -> None:
        assert self.channel_id is not None

        for i, chunk in enumerate(_split_message(text, max_len=1900)):
            payload: dict[str, Any] = {"content": chunk}
            if i == 0 and self.reply_as_reply and source_message_id:
                payload["message_reference"] = {
                    "message_id": source_message_id,
                    "channel_id": self.channel_id,
                }
            self._request("POST", f"/channels/{self.channel_id}/messages", payload, allow_retry=True)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        allow_retry: bool = False,
    ) -> Any:
        if not self.token:
            raise RuntimeError("discord token not configured")

        url = f"https://discord.com/api/v10{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None

        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bot {self.token}")
        if payload is not None:
            req.add_header("Content-Type", "application/json")

        attempts = 3 if allow_retry else 1
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    raw = resp.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempt < attempts - 1:
                    retry_after = _extract_retry_after(detail)
                    time.sleep(max(0.2, retry_after))
                    continue
                raise RuntimeError(f"discord HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                if attempt < attempts - 1:
                    time.sleep(1.0)
                    continue
                raise RuntimeError(f"discord request failed: {exc}") from exc

            if not raw.strip():
                return {}
            return json.loads(raw)

        raise RuntimeError("discord request failed after retries")

    @staticmethod
    def _extract_inbound(
        messages: list[dict[str, Any]],
        *,
        after_id: str,
        bot_user_id: str | None,
    ) -> tuple[list[DiscordInbound], str]:
        filtered: list[DiscordInbound] = []
        last_id = after_id

        for item in messages:
            message_id = str(item.get("id", "")).strip()
            if not message_id:
                continue

            if _snowflake_gt(message_id, last_id):
                last_id = message_id

            author = item.get("author")
            if isinstance(author, dict):
                if author.get("bot"):
                    continue
                if bot_user_id and str(author.get("id", "")) == bot_user_id:
                    continue

            content = str(item.get("content") or "").strip()
            if not content:
                continue

            filtered.append(DiscordInbound(message_id=message_id, content=content))

        filtered.sort(key=lambda m: int(m.message_id))
        return filtered, last_id


def _snowflake_gt(left: str, right: str) -> bool:
    try:
        return int(left) > int(right)
    except ValueError:
        return left > right


def _extract_retry_after(raw_json: str) -> float:
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return 1.0
    try:
        return float(payload.get("retry_after", 1.0))
    except (TypeError, ValueError):
        return 1.0


def _split_message(content: str, max_len: int = 1900) -> list[str]:
    text = content or ""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Try to split on a newline boundary within the limit
        cut = text.rfind("\n", 0, max_len + 1)
        if cut <= 0:
            # Try to split on a space boundary within the limit
            cut = text.rfind(" ", 0, max_len + 1)
        if cut <= 0:
            # No word boundary found — hard cut
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    return chunks
