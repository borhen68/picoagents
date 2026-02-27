from __future__ import annotations

from dataclasses import dataclass

from .base import Skill, SkillContext, SkillResult


@dataclass(slots=True)
class SkillDecision:
    skill_name: str | None
    best_score: float
    scores: dict[str, float]
    should_run: bool


class SkillRegistry:
    def __init__(self, threshold: float = 0.78) -> None:
        self.threshold = threshold
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(f"unknown skill: {name}")
        return self._skills[name]

    def names(self) -> list[str]:
        return sorted(self._skills)

    def decide(self, message: str, context: SkillContext) -> SkillDecision:
        if not self._skills:
            return SkillDecision(skill_name=None, best_score=0.0, scores={}, should_run=False)

        scores = {name: max(0.0, min(1.0, float(skill.score(message, context)))) for name, skill in self._skills.items()}
        best_name, best_score = max(scores.items(), key=lambda kv: kv[1])
        should_run = best_score >= self.threshold
        return SkillDecision(skill_name=best_name if should_run else None, best_score=best_score, scores=scores, should_run=should_run)

    async def run(self, skill_name: str, message: str, context: SkillContext) -> SkillResult:
        skill = self.get(skill_name)
        return await skill.run(message, context)
