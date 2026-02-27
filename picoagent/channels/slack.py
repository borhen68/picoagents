from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Awaitable, Callable


class SlackChannel:
    name = "slack"

    def __init__(
        self,
        *,
        token: str | None,
        channel_id: str | None,
        poll_seconds: float = 3.0,
        reply_in_thread: bool = True,
        timeout_seconds: int = 20,
    ) -> None:
        self.token = token
        self.channel_id = channel_id
        self.poll_seconds = poll_seconds
        self.reply_in_thread = reply_in_thread
        self.timeout_seconds = timeout_seconds
        self._bot_user_id: str | None = None

    async def start(self, handler: Callable[[str], Awaitable[str]]) -> None:
        if not self.token:
            raise RuntimeError("slack token not configured")
        if not self.channel_id:
            raise RuntimeError("slack channel_id not configured")

        self._bot_user_id = await asyncio.to_thread(self._get_bot_user_id)
        last_ts = await asyncio.to_thread(self._latest_ts)

        while True:
            messages = await asyncio.to_thread(self._fetch_messages, last_ts)
            for msg in messages:
                ts = str(msg.get("ts", "0"))
                if self._ts_gt(ts, last_ts):
                    last_ts = ts

                text = str(msg.get("text", "")).strip()
                if not text:
                    continue

                response = await handler(text)
                thread_ts = msg.get("thread_ts") or msg.get("ts") if self.reply_in_thread else None
                await asyncio.to_thread(self._post_message, response, thread_ts)

            await asyncio.sleep(self.poll_seconds)

    def _get_bot_user_id(self) -> str | None:
        data = self._api_call("auth.test", {})
        return str(data.get("user_id", "")) or None

    def _latest_ts(self) -> str:
        data = self._api_call("conversations.history", {"channel": self.channel_id, "limit": 1})
        messages = data.get("messages", [])
        if not messages:
            return "0"
        return str(messages[0].get("ts", "0"))

    def _fetch_messages(self, last_ts: str) -> list[dict[str, Any]]:
        data = self._api_call(
            "conversations.history",
            {
                "channel": self.channel_id,
                "limit": 20,
                "oldest": last_ts,
                "inclusive": False,
            },
        )

        raw = data.get("messages", [])
        messages: list[dict[str, Any]] = []
        for msg in raw:
            ts = str(msg.get("ts", "0"))
            if not self._ts_gt(ts, last_ts):
                continue
            if msg.get("subtype"):
                continue
            if msg.get("bot_id"):
                continue
            if self._bot_user_id and str(msg.get("user", "")) == self._bot_user_id:
                continue
            messages.append(msg)

        messages.sort(key=lambda m: float(str(m.get("ts", "0"))))
        return messages

    def _post_message(self, text: str, thread_ts: str | None) -> None:
        payload: dict[str, Any] = {"channel": self.channel_id, "text": text[:3900]}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        self._api_call("chat.postMessage", payload)

    def _api_call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError("slack token not configured")

        url = f"https://slack.com/api/{method}"
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json; charset=utf-8")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"slack HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"slack request failed: {exc}") from exc

        payload_obj = json.loads(body)
        if not payload_obj.get("ok"):
            raise RuntimeError(f"slack API error: {payload_obj.get('error', 'unknown_error')}")
        return payload_obj

    @staticmethod
    def _ts_gt(a: str, b: str) -> bool:
        try:
            return float(a) > float(b)
        except ValueError:
            return a > b
