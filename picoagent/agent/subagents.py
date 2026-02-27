from __future__ import annotations

import asyncio
from dataclasses import dataclass

from picoagent.core.scheduler import ToolDecision
from picoagent.providers.registry import ProviderClient


@dataclass(slots=True)
class SubagentResult:
    spawned: bool
    note: str = ""
    confidence: float = 0.0


class SubagentCoordinator:
    """Spawns a lightweight review subagent only when confidence is high enough."""

    def __init__(self, provider: ProviderClient, min_confidence: float = 0.8, max_chars: int = 900) -> None:
        self.provider = provider
        self.min_confidence = min_confidence
        self.max_chars = max_chars

    async def maybe_spawn(self, user_message: str, decision: ToolDecision, tool_output: str) -> SubagentResult:
        if decision.should_clarify or decision.tool_name is None:
            return SubagentResult(spawned=False)

        confidence = float(decision.probabilities.get(decision.tool_name, 0.0))
        if confidence < self.min_confidence:
            return SubagentResult(spawned=False, confidence=confidence)

        prompt = (
            f"User request:\n{user_message}\n\n"
            f"Primary tool: {decision.tool_name}\n"
            f"Tool output:\n{tool_output[:2200]}\n\n"
            "Provide a short second-opinion review with:\n"
            "1) one risk if any,\n"
            "2) one follow-up action."
        )

        try:
            note = await asyncio.to_thread(
                self.provider.chat,
                prompt,
                system_prompt="You are a cautious assistant. Keep output under 120 words.",
            )
        except Exception:  # noqa: BLE001
            return SubagentResult(spawned=False, confidence=confidence)

        clipped = note.strip()[: self.max_chars]
        return SubagentResult(spawned=bool(clipped), note=clipped, confidence=confidence)
