from __future__ import annotations

import json
from pathlib import Path

import pytest

from picoagent.agent.tools.search import SearchTool
from picoagent.agent.tools.registry import ToolContext


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.mark.asyncio
async def test_search_tool_returns_crypto_price_via_coingecko(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(req, timeout=15):  # noqa: ANN001
        url = getattr(req, "full_url", str(req))
        assert "coingecko.com" in url
        return _FakeResponse({"bitcoin": {"usd": 66754, "last_updated_at": 1700000000}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    tool = SearchTool(timeout_seconds=2)
    context = ToolContext(workspace_root=tmp_path, session_id="test")
    result = await tool.run({"query": "what is btc price today?"}, context)

    assert result.success is True
    assert "Bitcoin (BTC) price" in result.output
    assert "66,754.00 USD" in result.output
    assert "CoinGecko" in result.output


@pytest.mark.asyncio
async def test_search_tool_falls_back_to_ddg_for_non_price_queries(monkeypatch, tmp_path: Path) -> None:
    def fake_urlopen(req, timeout=15):  # noqa: ANN001
        url = getattr(req, "full_url", str(req))
        assert "duckduckgo.com" in url
        return _FakeResponse(
            {
                "Heading": "OpenAI",
                "AbstractText": "OpenAI is an AI research company.",
                "RelatedTopics": [],
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    tool = SearchTool(timeout_seconds=2)
    context = ToolContext(workspace_root=tmp_path, session_id="test")
    result = await tool.run({"query": "openai company"}, context)

    assert result.success is True
    assert "OpenAI: OpenAI is an AI research company." in result.output
