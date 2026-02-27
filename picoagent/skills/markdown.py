from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class MarkdownSkill:
    name: str
    path: Path
    description: str
    content: str


class MarkdownSkillLibrary:
    """Nanobot-style skill loader from SKILL.md files."""

    def __init__(self, skills_dir: str | Path) -> None:
        self.skills_dir = Path(skills_dir).expanduser()

    def list_skills(self) -> list[MarkdownSkill]:
        if not self.skills_dir.exists():
            return []

        skills: list[MarkdownSkill] = []
        for skill_file in sorted(self.skills_dir.rglob("SKILL.md")):
            if not skill_file.is_file():
                continue

            content = skill_file.read_text(encoding="utf-8", errors="replace").strip()
            if not content:
                continue

            name = skill_file.parent.name
            description = _extract_description(content)
            skills.append(MarkdownSkill(name=name, path=skill_file, description=description, content=content))

        return skills

    def summary(self) -> str:
        skills = self.list_skills()
        if not skills:
            return ""
        lines = ["Available skills:"]
        for skill in skills:
            lines.append(f"- {skill.name}: {skill.description}")
        return "\n".join(lines)

    def select_for_message(self, message: str, max_skills: int = 3) -> list[MarkdownSkill]:
        text = message.lower()
        available = self.list_skills()

        if not available:
            return []

        selected: list[MarkdownSkill] = []
        for skill in available:
            name = skill.name.lower()
            explicit = f"${name}" in text or re.search(rf"\b{name}\b", text)
            description_hit = any(word in text for word in _keywords(skill.description))
            if explicit or description_hit:
                selected.append(skill)

        if not selected:
            return []

        # Stable deterministic ordering by explicit mention first, then name.
        def rank(skill: MarkdownSkill) -> tuple[int, str]:
            name = skill.name.lower()
            explicit = 1 if (f"${name}" in text or re.search(rf"\b{name}\b", text)) else 0
            return (-explicit, name)

        selected.sort(key=rank)
        return selected[:max_skills]


def _extract_description(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return stripped[:180]
    return "Skill instructions"


def _keywords(description: str) -> set[str]:
    words = set(re.findall(r"[a-zA-Z0-9_]{4,}", description.lower()))
    stop = {
        "this",
        "that",
        "with",
        "from",
        "into",
        "about",
        "your",
        "when",
        "where",
        "which",
        "should",
        "would",
        "could",
        "skill",
        "instructions",
    }
    return {w for w in words if w not in stop}
