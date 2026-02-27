from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SessionMessage:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, data: dict) -> "SessionMessage":
        return cls(
            role=str(data.get("role", "user")),
            content=str(data.get("content", "")),
            timestamp=float(data.get("timestamp", time.time())),
        )


@dataclass(slots=True)
class SessionState:
    key: str
    messages: list[SessionMessage] = field(default_factory=list)
    last_consolidated: int = 0
    metadata: dict = field(default_factory=dict)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(SessionMessage(role=role, content=content))

    def get_history(self, max_messages: int = 50) -> list[dict[str, str]]:
        if max_messages <= 0:
            return []
        selected = self.messages[-max_messages:]
        return [{"role": m.role, "content": m.content} for m in selected]

    def clear(self) -> None:
        self.messages.clear()
        self.last_consolidated = 0

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "last_consolidated": self.last_consolidated,
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        key = str(data.get("key", "default"))
        messages = [SessionMessage.from_dict(item) for item in data.get("messages", []) if isinstance(item, dict)]
        last_consolidated = int(data.get("last_consolidated", 0))
        last_consolidated = max(0, min(last_consolidated, len(messages)))
        metadata = data.get("metadata", {})
        return cls(key=key, messages=messages, last_consolidated=last_consolidated, metadata=metadata)


class SessionManager:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else None
        self._sessions: dict[str, SessionState] = {}
        self.load()

    def get_or_create(self, key: str) -> SessionState:
        session = self._sessions.get(key)
        if session is None:
            session = SessionState(key=key)
            self._sessions[key] = session
        return session

    def save_session(self, session: SessionState) -> None:
        self._sessions[session.key] = session
        self.save()

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sessions": [session.to_dict() for session in self._sessions.values()],
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return

        sessions = raw.get("sessions", []) if isinstance(raw, dict) else []
        self._sessions = {}
        for item in sessions:
            if not isinstance(item, dict):
                continue
            session = SessionState.from_dict(item)
            self._sessions[session.key] = session

    def remove(self, key: str) -> bool:
        removed = self._sessions.pop(key, None) is not None
        if removed:
            self.save()
        return removed

    def keys(self) -> list[str]:
        return sorted(self._sessions)

    def __len__(self) -> int:
        return len(self._sessions)
