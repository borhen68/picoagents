from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

if TYPE_CHECKING:
    from picoagent.providers.base import LLMProvider
    from picoagent.session import SessionState



class DualMemoryStore:
    """Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (grep-searchable log)."""

    def __init__(self, workspace: Path, memory_dir_name: str = ".picoagent/memory"):
        self.memory_dir = ensure_dir(workspace / memory_dir_name)
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"

    def read_long_term(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")

    def get_memory_context(self) -> str:
        long_term = self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""

    async def consolidate(
        self,
        session: "SessionState",
        provider: "LLMProvider",
        model: str,
        *,
        archive_all: bool = False,
        memory_window: int = 50,
    ) -> bool:
        """Consolidate old messages into MEMORY.md + HISTORY.md via LLM tool call.

        Returns True on success (including no-op), False on failure.
        """
        # Note: session format in picoagent is different than nanobot. Picoagent uses Session turn objects.
        # We need to adapt it here.
        
        # Determine how many messages strictly to keep 
        keep_count = memory_window // 2
        messages = session.messages
        
        # We can just keep a simple metadata dict on the session manually if it doesn't exist
        if not hasattr(session, "metadata"):
            session.metadata = {}

        last_consolidated = session.metadata.get("dual_memory_consolidated", 0)
        
        if archive_all:
            old_messages = messages
        else:
            if len(messages) <= keep_count:
                return True
            if len(messages) - last_consolidated <= 0:
                return True
            old_messages = messages[last_consolidated:-keep_count]
            if not old_messages:
                return True

        lines = []
        for msg in old_messages:
            # Format [timestamp] ROLE: content
            from datetime import datetime
            time_str = datetime.fromtimestamp(msg.timestamp).strftime('%Y-%m-%d %H:%M')
            lines.append(f"[{time_str}] {msg.role.upper()}: {msg.content}")

        if not lines:
            return True

        current_memory = self.read_long_term()
        prompt = f"""Process this conversation and consolidate the memory.
Respond ONLY with a valid JSON schema containing exactly these two keys:
1. `history_entry`: A paragraph (2-5 sentences) summarizing key events/decisions/topics. Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search.
2. `memory_update`: Full updated long-term memory as markdown. Include all existing facts plus new ones. Return unchanged if nothing new.

Do not include markdown codeblocks or any other text before or after the JSON.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{chr(10).join(lines)}"""

        try:
            response = provider.chat(
                user_prompt=prompt,
                system_prompt="You are a memory consolidation agent. Return only valid JSON.",
            )

            # Attempt to parse out json block if LLM wrapped it
            raw_content = response.strip()
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            
            args = json.loads(raw_content.strip())
            
            if not isinstance(args, dict):
                return False

            if entry := args.get("history_entry"):
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                self.append_history(entry)
            if update := args.get("memory_update"):
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    self.write_long_term(update)

            session.metadata["dual_memory_consolidated"] = 0 if archive_all else len(messages) - keep_count
            return True
        except Exception:
            return False
