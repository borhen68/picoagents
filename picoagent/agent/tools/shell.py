from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from .registry import ToolContext, ToolResult


class ShellTool:
    name = "shell"
    description = "Run a shell command and return stdout/stderr. Args: {\"command\": str, \"timeout\": int?}."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "minLength": 1},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 600},
        },
        "required": ["command"],
    }

    def __init__(
        self,
        default_timeout: int = 20,
        restrict_to_workspace: bool = True,
        path_append: str = "",
        deny_patterns: list[str] | None = None,
    ) -> None:
        self.default_timeout = default_timeout
        self.restrict_to_workspace = restrict_to_workspace
        self.path_append = path_append
        self.deny_patterns = deny_patterns or [
            r"\brm\s+-[rf]{1,2}\b",          # rm -r, rm -rf, rm -fr
            r"\bdel\s+/[fq]\b",              # del /f, del /q
            r"\brmdir\s+/s\b",               # rmdir /s
            r"(?:^|[;&|]\s*)format\b",       # format
            r"\b(mkfs|diskpart)\b",          # disk operations
            r"\bdd\s+if=",                   # dd
            r">\s*/dev/sd",                  # write to disk
            r"\b(shutdown|reboot|poweroff)\b",  # system power
            r":\(\)\s*\{.*\};\s*:",          # fork bomb
            r"\|\s*(ba)?sh\b",               # pipe to shell (curl|bash, wget|sh)
            r"\|\s*zsh\b",                   # pipe to zsh
            r"\bsudo\b",                     # privilege escalation
            r"\bsu\s+-?\s",                  # switch user
            r"\beval\b",                     # eval command injection
            r"\bchmod\s+777\b",              # overly permissive permissions
            r">\s*/etc/",                    # writing to system config
            r"\bnc\s+-[el]",                 # netcat listeners (reverse shells)
        ]

    async def run(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        command = str(args.get("command", "")).strip()
        if not command:
            return ToolResult(output="missing command", success=False)

        cwd = str(context.workspace_root)
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return ToolResult(output=guard_error, success=False)

        env = os.environ.copy()
        if self.path_append:
            env["PATH"] = env.get("PATH", "") + os.pathsep + self.path_append

        timeout = int(args.get("timeout", self.default_timeout))
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(output=f"command timed out after {timeout}s", success=False)

        stdout = stdout_b.decode("utf-8", errors="replace").strip()
        stderr = stderr_b.decode("utf-8", errors="replace").strip()

        output = stdout
        if stderr:
            output = f"{stdout}\n{stderr}".strip()
        if not output:
            output = "(no output)"

        return ToolResult(
            output=output,
            success=proc.returncode == 0,
            metadata={"returncode": proc.returncode},
        )

    def _guard_command(self, command: str, cwd: str) -> str | None:
        cmd = command.strip()
        lower = cmd.lower()

        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"

        if self.restrict_to_workspace:
            # Block any explicit parent directory references
            if re.search(r"(?:^|\s)\.\.(?:$|/|\\)", cmd):
                return "Error: Command blocked by safety guard (path traversal detected)"

            cwd_path = Path(cwd).resolve()
            win_paths = re.findall(r"[A-Za-z]:\\[^\\\"']+", cmd)
            posix_paths = re.findall(r"(?:^|[\s|>])(/[^\s\"'>]+)", cmd)

            for raw in win_paths + posix_paths:
                try:
                    p = Path(raw.strip()).resolve()
                except Exception:
                    continue
                if p.is_absolute() and cwd_path not in p.parents and p != cwd_path:
                    return "Error: Command blocked by safety guard (path outside working dir)"

        return None
