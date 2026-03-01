from __future__ import annotations

from datetime import datetime, timezone
import json
import re
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

    _CRYPTO_MAP = {
        "btc": ("bitcoin", "BTC", "Bitcoin"),
        "bitcoin": ("bitcoin", "BTC", "Bitcoin"),
        "eth": ("ethereum", "ETH", "Ethereum"),
        "ethereum": ("ethereum", "ETH", "Ethereum"),
        "sol": ("solana", "SOL", "Solana"),
        "solana": ("solana", "SOL", "Solana"),
        "doge": ("dogecoin", "DOGE", "Dogecoin"),
        "dogecoin": ("dogecoin", "DOGE", "Dogecoin"),
        "xrp": ("ripple", "XRP", "XRP"),
        "ada": ("cardano", "ADA", "Cardano"),
        "ltc": ("litecoin", "LTC", "Litecoin"),
        "bnb": ("binancecoin", "BNB", "BNB"),
    }

    _QUOTE_MAP = {
        "usd": "usd",
        "usdt": "usd",
        "dollar": "usd",
        "dollars": "usd",
        "eur": "eur",
        "euro": "eur",
        "euros": "eur",
        "gbp": "gbp",
        "pound": "gbp",
        "pounds": "gbp",
        "tnd": "tnd",
        "dinar": "tnd",
    }

    def _maybe_crypto_query(self, query: str) -> tuple[str, str, str, str] | None:
        text = query.lower()
        if not any(k in text for k in ("price", "worth", "rate", "quote", "market")):
            return None

        coin_info: tuple[str, str, str] | None = None
        for token, info in self._CRYPTO_MAP.items():
            if re.search(rf"\b{re.escape(token)}\b", text):
                coin_info = info
                break
        if coin_info is None:
            return None

        quote = "usd"
        for token, symbol in self._QUOTE_MAP.items():
            if re.search(rf"\b{re.escape(token)}\b", text):
                quote = symbol
                break

        coin_id, ticker, name = coin_info
        return coin_id, ticker, name, quote

    def _fetch_crypto_price(self, query: str) -> str | None:
        parsed = self._maybe_crypto_query(query)
        if parsed is None:
            return None

        coin_id, ticker, coin_name, quote = parsed
        url = "https://api.coingecko.com/api/v3/simple/price?" + urllib.parse.urlencode(
            {
                "ids": coin_id,
                "vs_currencies": quote,
                "include_last_updated_at": "true",
            }
        )
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

        coin_payload = payload.get(coin_id)
        if not isinstance(coin_payload, dict):
            return None
        value = coin_payload.get(quote)
        if not isinstance(value, (int, float)):
            return None

        quote_upper = quote.upper()
        price_text = f"{float(value):,.2f}" if float(value) >= 1 else f"{float(value):.6f}"
        updated_at = coin_payload.get("last_updated_at")
        if isinstance(updated_at, (int, float)) and updated_at > 0:
            updated = datetime.fromtimestamp(float(updated_at), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            return f"{coin_name} ({ticker}) price: {price_text} {quote_upper}. Source: CoinGecko ({updated})."
        return f"{coin_name} ({ticker}) price: {price_text} {quote_upper}. Source: CoinGecko."

    async def run(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(output="missing query", success=False)

        crypto_result = self._fetch_crypto_price(query)
        if crypto_result is not None:
            return ToolResult(output=crypto_result, success=True)

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
