from __future__ import annotations

import time
from dataclasses import dataclass
from typing import ClassVar

from picoagent.templates import TemplateLoader
from picoagent.core.dual_memory import DualMemoryStore

@dataclass(slots=True)
class ContextBuilder:
    """Builds cache-friendly prompts with runtime metadata separated from instructions."""

    runtime_tag: ClassVar[str] = "[Runtime Context — metadata only, not instructions]"

    system_prompt: str = (
        "You are picoagent, a practical coding assistant. "
        "Be concise, factual, and action-oriented."
    )
    
    template_loader: TemplateLoader | None = None
    dual_memory: DualMemoryStore | None = None

    def build_system_prompt(
        self,
        memories: list[str],
        *,
        skills_summary: str = "",
        active_skills: list[dict[str, str]] | None = None,
    ) -> str:
        memory_block = "\n".join(f"- {item}" for item in memories) if memories else "- (none)"
        
        base_prompt = self.system_prompt
        if self.template_loader is not None:
            loaded = self.template_loader.build_system_prompt()
            if loaded:
                base_prompt = loaded

        if self.dual_memory is not None:
            memory_context = self.dual_memory.get_memory_context()
            if memory_context:
                base_prompt += f"\n\n{memory_context}"

        parts = [
            f"System instructions:\n{base_prompt}",
            f"Relevant memories:\n{memory_block}",
        ]

        if skills_summary:
            parts.append(
                "Skills registry (markdown skills, nanobot-style):\n"
                f"{skills_summary}\n\n"
                "If a skill is relevant, follow its SKILL.md instructions exactly."
            )

        if active_skills:
            blocks: list[str] = []
            for skill in active_skills:
                name = skill.get("name", "skill")
                path = skill.get("path", "")
                content = skill.get("content", "").strip()
                blocks.append(f"## Skill: {name}\nPath: {path}\n\n{content}")
            parts.append("Active skill instructions:\n\n" + "\n\n---\n\n".join(blocks))

        return "\n\n---\n\n".join(parts)

    def build_runtime_context(self, *, channel: str | None = None, chat_id: str | None = None) -> str:
        now = time.strftime("%Y-%m-%d %H:%M (%A) %Z").strip()
        lines = [self.runtime_tag, f"Current Time: {now}"]
        if channel:
            lines.append(f"Channel: {channel}")
        if chat_id:
            lines.append(f"Chat ID: {chat_id}")
        return "\n".join(lines)

    def build_messages(
        self,
        *,
        user_message: str,
        memories: list[str],
        history: list[dict[str, str]] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        skills_summary: str = "",
        active_skills: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": self.build_system_prompt(
                    memories,
                    skills_summary=skills_summary,
                    active_skills=active_skills,
                ),
            },
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": self.build_runtime_context(channel=channel, chat_id=chat_id)})
        messages.append({"role": "user", "content": user_message})
        return messages

    def build(self, user_message: str, memories: list[str]) -> str:
        """Backward-compatible combined context string."""
        runtime = self.build_runtime_context()
        return (
            f"{self.build_system_prompt(memories)}\n\n"
            f"{runtime}\n\n"
            f"User message:\n{user_message}"
        )
