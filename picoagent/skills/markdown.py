from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class MarkdownSkill:
    name: str
    path: Path
    description: str
    content: str
    requires: list[str] = field(default_factory=list)


class MarkdownSkillLibrary:
    """Nanobot-style skill loader from SKILL.md files."""

    def __init__(self, skills_dir: str | Path) -> None:
        self.skills_dir = Path(skills_dir).expanduser()
        self._mtime_cache: dict[str, float] = {}

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
            requires = _extract_requires(content)
            skills.append(MarkdownSkill(name=name, path=skill_file, description=description, content=content, requires=requires))

        return skills

    def reload_if_changed(self) -> int:
        """Re-scan skill files, reload only those whose mtime has changed.

        Returns the count of reloaded skills.
        """
        if not self.skills_dir.exists():
            return 0

        reloaded = 0
        for skill_file in sorted(self.skills_dir.rglob("SKILL.md")):
            if not skill_file.is_file():
                continue
            key = str(skill_file)
            try:
                mtime = skill_file.stat().st_mtime
            except OSError:
                continue
            if self._mtime_cache.get(key) != mtime:
                self._mtime_cache[key] = mtime
                reloaded += 1
        return reloaded

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

        # Build a name->skill map for dependency resolution
        skill_by_name: dict[str, MarkdownSkill] = {s.name: s for s in available}

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
        selected = selected[:max_skills]

        # Include required dependencies (one level deep, no recursion)
        selected_names = {s.name for s in selected}
        deps_to_add: list[MarkdownSkill] = []
        for skill in selected:
            for req_name in skill.requires:
                if req_name not in selected_names and req_name in skill_by_name:
                    deps_to_add.append(skill_by_name[req_name])
                    selected_names.add(req_name)

        # Merge deps, still respect max_active_skills limit
        combined = selected + deps_to_add
        combined = combined[:max_skills]

        # Record telemetry
        self._record_usage([s.name for s in combined])

        return combined

    def _record_usage(self, skill_names: list[str]) -> None:
        """Append each selected skill's name + timestamp to ~/.picoagent/skill_usage.jsonl."""
        if not skill_names:
            return
        usage_file = Path.home() / ".picoagent" / "skill_usage.jsonl"
        try:
            usage_file.parent.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(tz=timezone.utc).isoformat()
            with open(usage_file, "a", encoding="utf-8") as f:
                for name in skill_names:
                    f.write(json.dumps({"skill": name, "ts": ts}) + "\n")
        except OSError:
            pass

    def get_usage_stats(self) -> dict[str, int]:
        """Read skill_usage.jsonl and return {skill_name: count} dict."""
        usage_file = Path.home() / ".picoagent" / "skill_usage.jsonl"
        counts: dict[str, int] = {}
        if not usage_file.exists():
            return counts
        try:
            for line in usage_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    skill = obj.get("skill")
                    if isinstance(skill, str):
                        counts[skill] = counts.get(skill, 0) + 1
                except (json.JSONDecodeError, AttributeError):
                    continue
        except OSError:
            pass
        return counts


def _extract_description(content: str) -> str:
    # Skip frontmatter block if present
    lines = content.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return stripped[:180]
    return "Skill instructions"


def _extract_requires(content: str) -> list[str]:
    """Extract 'requires' list from YAML frontmatter using stdlib re."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    # Find end of frontmatter
    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end == -1:
        return []
    frontmatter = "\n".join(lines[1:end])
    # Match: requires: [skill-a, skill-b]
    m = re.search(r"^requires\s*:\s*\[([^\]]*)\]", frontmatter, re.MULTILINE)
    if m:
        items = [item.strip().strip("'\"") for item in m.group(1).split(",")]
        return [item for item in items if item]
    return []


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
