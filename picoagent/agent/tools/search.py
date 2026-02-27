from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from .registry import ToolContext, ToolResult


class SearchTool:
    name = "search"
    description = "Search the public web for a query using DuckDuckGo instant answer API. Args: {\"query\": str}."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1},
        },
        "required": ["query"],
    }

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    async def run(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(output="missing query", success=False)

        url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {
                "q": query,
                "format": "json",
                "no_redirect": 1,
                "no_html": 1,
                "skip_disambig": 1,
            }
        )

        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(output=f"search request failed: {exc}", success=False)

        lines: list[str] = []
        heading = payload.get("Heading")
        abstract = payload.get("AbstractText")
        if heading or abstract:
            lines.append(f"{heading}: {abstract}".strip(": "))

        for topic in payload.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and "Text" in topic:
                text = str(topic.get("Text", "")).strip()
                first_url = str(topic.get("FirstURL", "")).strip()
                if text:
                    lines.append(f"- {text} ({first_url})" if first_url else f"- {text}")

        if not lines:
            lines.append("No results from instant-answer API. Try a more specific query.")

        return ToolResult(output="\n".join(lines), success=True)
