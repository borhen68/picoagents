from __future__ import annotations

import asyncio
import email
import imaplib
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import default
from email.utils import parseaddr
from typing import Awaitable, Callable


@dataclass(slots=True)
class InboundEmail:
    sender: str
    subject: str
    body: str


class EmailChannel:
    name = "email"

    def __init__(
        self,
        *,
        username: str | None,
        password: str | None,
        imap_host: str | None,
        smtp_host: str | None,
        from_address: str | None = None,
        imap_port: int = 993,
        smtp_port: int = 587,
        folder: str = "INBOX",
        poll_seconds: float = 15.0,
        use_tls: bool = True,
        use_ssl: bool = False,
        allow_from: set[str] | None = None,
    ) -> None:
        self.username = username
        self.password = password
        self.imap_host = imap_host
        self.smtp_host = smtp_host
        self.from_address = from_address
        self.imap_port = imap_port
        self.smtp_port = smtp_port
        self.folder = folder
        self.poll_seconds = poll_seconds
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.allow_from = allow_from

    async def start(self, handler: Callable[[str], Awaitable[str]]) -> None:
        if not self.username or not self.password:
            raise RuntimeError("email username/password not configured")
        if not self.imap_host or not self.smtp_host:
            raise RuntimeError("email imap_host/smtp_host not configured")

        while True:
            try:
                inbound = await asyncio.to_thread(self._fetch_unseen)
            except Exception:
                await asyncio.sleep(self.poll_seconds)
                continue

            for msg in inbound:
                if not msg.body.strip():
                    continue
                if self.allow_from and msg.sender not in self.allow_from:
                    continue
                response = await handler(msg.body)
                await asyncio.to_thread(self._send_reply, msg.sender, msg.subject, response)

            await asyncio.sleep(self.poll_seconds)

    def _fetch_unseen(self) -> list[InboundEmail]:
        assert self.username is not None
        assert self.password is not None
        assert self.imap_host is not None

        results: list[InboundEmail] = []
        conn = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        try:
            conn.login(self.username, self.password)
            conn.select(self.folder)
            status, data = conn.search(None, "UNSEEN")
            if status != "OK" or not data:
                return []

            ids = data[0].split()
            for msg_id in ids:
                fetch_status, payload = conn.fetch(msg_id, "(RFC822)")
                if fetch_status != "OK" or not payload:
                    continue

                raw = b""
                for item in payload:
                    if isinstance(item, tuple) and item[1]:
                        raw = item[1]
                        break
                if not raw:
                    continue

                parsed = email.message_from_bytes(raw, policy=default)
                sender = parseaddr(parsed.get("From", ""))[1]
                subject = str(parsed.get("Subject", "")).strip()
                body = self._extract_body(parsed)
                if sender and body.strip():
                    results.append(InboundEmail(sender=sender, subject=subject, body=body))

                conn.store(msg_id, "+FLAGS", "\\Seen")
        finally:
            try:
                conn.close()
            except Exception:
                pass
            conn.logout()

        return results

    def _send_reply(self, recipient: str, source_subject: str, body: str) -> None:
        assert self.username is not None
        assert self.password is not None
        assert self.smtp_host is not None

        msg = EmailMessage()
        msg["From"] = self.from_address or self.username
        msg["To"] = recipient
        msg["Subject"] = self._reply_subject(source_subject)
        msg.set_content(body)

        if self.use_ssl:
            smtp = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=20)
        else:
            smtp = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20)

        with smtp:
            if self.use_tls and not self.use_ssl:
                smtp.starttls()
            smtp.login(self.username, self.password)
            smtp.send_message(msg)

    @staticmethod
    def _reply_subject(subject: str) -> str:
        clean = subject.strip()
        if not clean:
            return "Re: picoagent"
        if clean.lower().startswith("re:"):
            return clean
        return f"Re: {clean}"

    @staticmethod
    def _extract_body(message: email.message.EmailMessage) -> str:
        if message.is_multipart():
            parts: list[str] = []
            for part in message.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get_content_disposition() == "attachment":
                    continue
                if part.get_content_type() == "text/plain":
                    try:
                        parts.append(part.get_content())
                    except Exception:
                        continue
            if parts:
                return "\n".join(p.strip() for p in parts if p and p.strip())
            return ""

        try:
            content = message.get_content()
        except Exception:
            return ""
        return content if isinstance(content, str) else str(content)
