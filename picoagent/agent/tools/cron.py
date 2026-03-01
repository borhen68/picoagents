from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from picoagent.agent.tools.registry import ToolContext, ToolResult
from picoagent.config import DEFAULT_CRON_PATH
from picoagent.cron import CronRunner, CronTask


class CronTool:
    """Tool to manage recurring or scheduled Background tasks using picoagent's CronRunner."""

    name = "cron"
    description = (
        "CRITICAL TOOL FOR RECURRING TASKS AND REMINDERS. "
        "Use this tool whenever the user asks you to 'remind me', 'do this every X minutes', "
        "or schedule any kind of repeated background task. "
        "Action='add' creates a new loop. Action='list' shows them. Action='remove' stops them."
    )
    
    # Do not cache cron operations, they are stateful
    cacheable = False

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "remove"],
                "description": "What to do: add, list, or remove.",
            },
            "message": {
                "type": "string",
                "description": "The prompt/message to execute when the task fires. Required for 'add'.",
            },
            "every_seconds": {
                "type": "number",
                "description": "Interval in seconds for recurring tasks. Required for 'add'.",
            },
            "job_id": {
                "type": "string",
                "description": "The ID of the task to remove. Required for 'remove'.",
            },
        },
        "required": ["action"],
    }

    @staticmethod
    def _coerce_action(args: dict[str, Any]) -> str:
        raw = str(args.get("action", "")).strip().lower()
        alias = {
            "create": "add",
            "new": "add",
            "delete": "remove",
        }
        return alias.get(raw, raw)

    @staticmethod
    def _coerce_message(args: dict[str, Any]) -> str:
        for key in ("message", "prompt", "text", "reminder", "reminder_message"):
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _coerce_every_seconds(args: dict[str, Any]) -> float | None:
        for key in ("every_seconds", "everyseconds", "everySeconds", "interval_seconds", "intervalSeconds"):
            value = args.get(key)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                text = value.strip()
                if not text:
                    continue
                try:
                    return float(text)
                except ValueError:
                    pass
                match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(s|sec|second|seconds|m|min|minute|minutes|h|hr|hour|hours)", text.lower())
                if not match:
                    continue
                amount = float(match.group(1))
                unit = match.group(2)
                if unit.startswith(("h", "hr", "hour")):
                    return amount * 3600
                if unit.startswith(("m", "min", "minute")):
                    return amount * 60
                return amount
        return None

    @staticmethod
    def _coerce_job_id(args: dict[str, Any]) -> str:
        for key in ("job_id", "jobId", "task_id", "taskId", "id"):
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    async def run(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        action = self._coerce_action(args)
        cron_path = context.cron_file or Path(DEFAULT_CRON_PATH).expanduser()
        runner = CronRunner(cron_path)
        runner.load()

        if action == "list":
            if not runner.state.tasks:
                return ToolResult("No active cron tasks.")
            lines = ["Active cron tasks:"]
            for task in runner.state.tasks:
                lines.append(f"- [{task.name}] Every {task.interval_seconds}s: {task.prompt}")
            return ToolResult("\n".join(lines))

        elif action == "remove":
            job_id = self._coerce_job_id(args)
            if not job_id:
                return ToolResult("job_id is required to remove a task.", success=False)
            
            initial_count = len(runner.state.tasks)
            runner.state.tasks = [t for t in runner.state.tasks if t.name != job_id]
            
            if len(runner.state.tasks) < initial_count:
                runner.save()
                return ToolResult(f"Removed task {job_id}")
            else:
                return ToolResult(f"Task {job_id} not found.", success=False)

        elif action == "add":
            message = self._coerce_message(args)
            every_seconds = self._coerce_every_seconds(args)
            
            if not message:
                return ToolResult("message is required to add a task.", success=False)
            if not isinstance(every_seconds, (int, float)) or every_seconds <= 0:
                return ToolResult("every_seconds must be a positive number.", success=False)

            job_id = str(uuid.uuid4())[:8]
            new_task = CronTask(
                name=job_id,
                prompt=message,
                interval_seconds=int(every_seconds),
                enabled=True,
                last_run=0.0, # Will trigger immediately on next poll
            )
            runner.state.tasks.append(new_task)
            runner.save()
            return ToolResult(f"Added task {job_id}: '{message}' every {every_seconds} seconds.")

        return ToolResult(f"Unknown action: {action}", success=False)
