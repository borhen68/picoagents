from __future__ import annotations

from pathlib import Path

from .base import SkillContext, SkillResult


class ProjectMapSkill:
    name = "project_map"
    description = "Build a quick map of repository files and folders when user asks about project structure."

    _keywords = {
        "project",
        "structure",
        "architecture",
        "files",
        "folders",
        "repository",
        "repo",
        "map",
        "overview",
    }

    def score(self, message: str, context: SkillContext) -> float:
        text = message.lower()
        hits = sum(1 for keyword in self._keywords if keyword in text)
        if hits == 0:
            return 0.0
        return min(1.0, 0.35 + 0.15 * hits)

    async def run(self, message: str, context: SkillContext) -> SkillResult:
        root = context.workspace_root
        entries: list[str] = []

        for path in sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if path.name.startswith("."):
                continue
            suffix = "/" if path.is_dir() else ""
            entries.append(path.name + suffix)

        if not entries:
            output = "Project root is empty."
        else:
            lines = ["Project map:"]
            lines.extend(f"- {name}" for name in entries[:40])
            if len(entries) > 40:
                lines.append(f"- ... {len(entries) - 40} more entries")
            output = "\n".join(lines)

        return SkillResult(output=output, confidence=0.85, metadata={"skill": self.name, "root": str(root)})


class ReadmeSkill:
    name = "readme_lookup"
    description = "Read README-like docs when user asks for setup, usage, or docs summary."

    _keywords = {"readme", "docs", "documentation", "install", "usage", "how to"}

    def score(self, message: str, context: SkillContext) -> float:
        text = message.lower()
        hits = sum(1 for keyword in self._keywords if keyword in text)
        if hits == 0:
            return 0.0
        return min(1.0, 0.3 + 0.2 * hits)

    async def run(self, message: str, context: SkillContext) -> SkillResult:
        root = context.workspace_root
        candidates = [
            root / "README.md",
            root / "README",
            root / "docs" / "README.md",
        ]

        selected: Path | None = None
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                selected = candidate
                break

        if selected is None:
            return SkillResult(output="No README file found in the workspace.", confidence=0.6, metadata={"skill": self.name})

        text = selected.read_text(encoding="utf-8", errors="replace")
        excerpt = text[:2200].strip()
        if len(text) > len(excerpt):
            excerpt += "\n\n...(truncated)"

        return SkillResult(
            output=f"README excerpt from {selected}:\n\n{excerpt}",
            confidence=0.8,
            metadata={"skill": self.name, "path": str(selected)},
        )
