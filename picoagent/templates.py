from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class TemplateLoader:
    """
    Loads nanobot-style templates (SOUL.md, USER.md, AGENTS.md) to customize
    the agent's personality, preferences, and instructions.
    
    If workspace templates exist, they override the built-in defaults.
    """

    workspace_root: Path
    templates_dir_name: str = "templates"

    def _get_builtin_dir(self) -> Path:
        return Path(__file__).parent / "templates"

    def _get_workspace_dir(self) -> Path:
        return self.workspace_root / self.templates_dir_name

    def load_template(self, name: str) -> str | None:
        """Looks for a template by name (e.g. 'SOUL.md') in workspace first, then builtin."""
        workspace_path = self._get_workspace_dir() / name
        if workspace_path.exists() and workspace_path.is_file():
            return self._strip_frontmatter(workspace_path.read_text(encoding="utf-8", errors="replace"))

        builtin_path = self._get_builtin_dir() / name
        if builtin_path.exists() and builtin_path.is_file():
            return self._strip_frontmatter(builtin_path.read_text(encoding="utf-8", errors="replace"))

        return None

    def build_system_prompt(self) -> str | None:
        """
        Merges SOUL.md, USER.md, and AGENTS.md into a single system instruction.
        Returns None if no templates were found.
        """
        parts = []

        soul = self.load_template("SOUL.md")
        if soul:
            parts.append(soul)

        user = self.load_template("USER.md")
        if user:
            parts.append(user)

        agents = self.load_template("AGENTS.md")
        if agents:
            parts.append(agents)

        if not parts:
            return None

        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        """Strips nanobot-style YAML frontmatter from markdown content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, flags=re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content.strip()
