from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(slots=True)
class SkillContext:
    workspace_root: Path
    memories: list[str]
    session_id: str | None = None


@dataclass(slots=True)
class SkillResult:
    output: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class Skill(Protocol):
    name: str
    description: str

    def score(self, message: str, context: SkillContext) -> float:
        ...

    async def run(self, message: str, context: SkillContext) -> SkillResult:
        ...
