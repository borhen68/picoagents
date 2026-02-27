from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

try:
    import websockets
except ImportError:
    websockets = None



@dataclass(slots=True)
class WhatsAppInbound:
    sender: str
    text: str
    raw: dict[str, Any]


class WhatsAppChannel:
    name = "whatsapp"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        phone_number_id: str | None = None,
        inbox_path: str | Path | None = None,
        outbox_path: str | Path | None = None,
        cursor_path: str | Path | None = None,
        bridge_url: str | None = None,
        bridge_token: str | None = None,
        poll_seconds: float = 3.0,
        timeout_seconds: int = 20,
    ) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.inbox_path = Path(inbox_path).expanduser() if inbox_path else None
        self.outbox_path = Path(outbox_path).expanduser() if outbox_path else None
        
        if cursor_path:
            self.cursor_path = Path(cursor_path).expanduser()
        elif self.inbox_path:
            self.cursor_path = self.inbox_path.with_suffix(".cursor")
        else:
            self.cursor_path = None
            
        self.bridge_url = bridge_url
        self.bridge_token = bridge_token
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        
        self._ws = None
        self._connected = False

    async def start(self, handler: Callable[[str], Awaitable[str]]) -> None:
        if self.bridge_url:
            await self._start_bridge(handler)
        elif self.inbox_path:
            await self._start_file_polling(handler)
        else:
            raise RuntimeError("whatsapp channel requires either bridge_url or inbox_path")

    async def _start_bridge(self, handler: Callable[[str], Awaitable[str]]) -> None:
        if websockets is None:
            raise RuntimeError("websockets module is required for whatsapp bridge")
        
        import logging
        logger = logging.getLogger("picoagent.whatsapp")
        
        while True:
            try:
                logger.info(f"Connecting to WhatsApp bridge at {self.bridge_url}...")
                async with websockets.connect(self.bridge_url) as ws:
                    self._ws = ws
                    self._connected = True
                    if self.bridge_token:
                        await ws.send(json.dumps({"type": "auth", "token": self.bridge_token}))
                    
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            msg_type = data.get("type")
                            
                            if msg_type == "message":
                                sender = data.get("sender", "") or data.get("pn", "")
                                content = data.get("content", "")
                                
                                if content.strip():
                                    response = await handler(content)
                                    payload = {
                                        "type": "send",
                                        "to": sender,
                                        "text": response
                                    }
                                    await ws.send(json.dumps(payload, ensure_ascii=False))
                            elif msg_type == "qr":
                                print("\n📱 Scan this QR code with WhatsApp (Linked Devices):")
                                print("--> Check the bridge terminal for the QR image <--\n")
                            elif msg_type == "status":
                                logger.info(f"WhatsApp status: {data.get('status')}")
                                
                        except Exception as e:
                            logger.error(f"Error handling bridge message: {e}")
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._ws = None
                logger.warning(f"WhatsApp bridge connection error: {e}. Reconnecting in {self.poll_seconds}s...")
                await asyncio.sleep(self.poll_seconds)

    async def _start_file_polling(self, handler: Callable[[str], Awaitable[str]]) -> None:
        if not self.inbox_path:
            return
        self.inbox_path.parent.mkdir(parents=True, exist_ok=True)
        self.inbox_path.touch(exist_ok=True)
        cursor = self._load_cursor()

        while True:
            messages, cursor = await asyncio.to_thread(self._read_new_messages, cursor)
            self._save_cursor(cursor)

            for message in messages:
                text = message.text.strip()
                if not text:
                    continue

                response = await handler(text)
                sender = message.sender.strip()
                if sender and self.access_token and self.phone_number_id:
                    await asyncio.to_thread(self._send_cloud_message, sender, response)
                elif self.outbox_path is not None:
                    await asyncio.to_thread(self._append_outbox, sender, response, message.raw)

            await asyncio.sleep(self.poll_seconds)

    def _read_new_messages(self, cursor: int) -> tuple[list[WhatsAppInbound], int]:
        lines = self.inbox_path.read_text(encoding="utf-8").splitlines()
        if cursor >= len(lines):
            return [], len(lines)

        inbound: list[WhatsAppInbound] = []
        for line in lines[cursor:]:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            text = str(data.get("text") or data.get("body") or "")
            sender = str(data.get("from") or data.get("sender") or "")
            if not text:
                continue

            inbound.append(WhatsAppInbound(sender=sender, text=text, raw=data))

        return inbound, len(lines)

    def _append_outbox(self, sender: str, response: str, source: dict[str, Any]) -> None:
        if self.outbox_path is None:
            return
        self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"to": sender, "text": response, "source": source}
        with self.outbox_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def _send_cloud_message(self, recipient: str, text: str) -> None:
        if not self.access_token or not self.phone_number_id:
            raise RuntimeError("whatsapp cloud token or phone_number_id not configured")

        url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": text[:4096]},
        }
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {self.access_token}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"whatsapp HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"whatsapp request failed: {exc}") from exc

        data_obj = json.loads(body)
        if data_obj.get("error"):
            raise RuntimeError(f"whatsapp API error: {data_obj['error']}")

    def _load_cursor(self) -> int:
        if not self.cursor_path.exists():
            return 0
        try:
            return int(self.cursor_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            return 0

    def _save_cursor(self, cursor: int) -> None:
        self.cursor_path.parent.mkdir(parents=True, exist_ok=True)
        self.cursor_path.write_text(str(max(cursor, 0)), encoding="utf-8")
