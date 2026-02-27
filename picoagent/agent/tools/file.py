from __future__ import annotations

from pathlib import Path
from typing import Any

from .registry import ToolContext, ToolResult


class FileTool:
    name = "file"
    description = (
        "Read, write, append, or list files inside workspace root. "
        "Args: {\"action\": \"read|write|append|list\", \"path\": str, \"content\": str?}."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["read", "write", "append", "list"]},
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
    }

    def __init__(self, max_read_bytes: int = 64_000, restrict_to_workspace: bool = True) -> None:
        self.max_read_bytes = max_read_bytes
        self.restrict_to_workspace = restrict_to_workspace

    async def run(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        action = str(args.get("action", "read")).lower().strip()
        raw_path = str(args.get("path", "")).strip()
        content = str(args.get("content", ""))

        try:
            target_dir = self._resolve_path(raw_path or ".", context.workspace_root) if action == "list" else None
            path = self._resolve_path(raw_path, context.workspace_root) if raw_path else None
        except ValueError as exc:
            return ToolResult(output=str(exc), success=False)

        if action == "list":
            assert target_dir is not None
            if not target_dir.exists() or not target_dir.is_dir():
                return ToolResult(output=f"not a directory: {target_dir}", success=False)
            items = sorted(p.name + ("/" if p.is_dir() else "") for p in target_dir.iterdir())
            return ToolResult(output="\n".join(items) if items else "(empty directory)", success=True)

        if not raw_path:
            return ToolResult(output="missing path", success=False)
        assert path is not None

        if action == "read":
            if not path.exists() or not path.is_file():
                return ToolResult(output=f"file not found: {path}", success=False)
            data = path.read_bytes()[: self.max_read_bytes]
            return ToolResult(output=data.decode("utf-8", errors="replace"), success=True)

        if action == "write":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(output=f"wrote {len(content)} chars to {path}", success=True)

        if action == "append":
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(output=f"appended {len(content)} chars to {path}", success=True)

        return ToolResult(output=f"unsupported action: {action}", success=False)

    def _resolve_path(self, raw_path: str, root: Path) -> Path:
        candidate = (root / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path).resolve()
        
        if self.restrict_to_workspace:
            root_resolved = root.resolve()
            if root_resolved not in candidate.parents and candidate != root_resolved:
                raise ValueError(f"path escapes workspace root: {raw_path}")
                
        return candidate
