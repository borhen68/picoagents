from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from picoagent.config import AgentConfig


class ProviderError(RuntimeError):
    pass


class ProviderClient(Protocol):
    def embed(self, text: str) -> np.ndarray:
        ...

    def score_tools(self, message: str, tool_docs: dict[str, str]) -> dict[str, float]:
        ...

    def plan_tool_args(self, message: str, tool_name: str, tool_doc: str) -> dict[str, Any]:
        ...

    def synthesize_response(
        self,
        user_message: str,
        tool_name: str,
        tool_result: str,
        memories: list[str],
    ) -> str:
        ...

    def chat(self, user_prompt: str, *, system_prompt: str | None = None) -> str:
        ...


@dataclass(slots=True)
class ProviderSpec:
    name: str
    base_url: str
    default_chat_model: str
    default_embedding_model: str
    api_key_env: str
    api_style: str = "openai"
    notes: str = ""


class SplitProviderClient:
    """Use one provider for chat/routing and another for embeddings."""

    def __init__(self, *, chat_client: ProviderClient, embedding_client: ProviderClient) -> None:
        self._chat = chat_client
        self._embed = embedding_client

    def embed(self, text: str) -> np.ndarray:
        return self._embed.embed(text)

    def score_tools(self, message: str, tool_docs: dict[str, str]) -> dict[str, float]:
        return self._chat.score_tools(message, tool_docs)

    def plan_tool_args(self, message: str, tool_name: str, tool_doc: str) -> dict[str, Any]:
        return self._chat.plan_tool_args(message, tool_name, tool_doc)

    def synthesize_response(
        self,
        user_message: str,
        tool_name: str,
        tool_result: str,
        memories: list[str],
    ) -> str:
        return self._chat.synthesize_response(user_message, tool_name, tool_result, memories)

    def chat(self, user_prompt: str, *, system_prompt: str | None = None) -> str:
        return self._chat.chat(user_prompt, system_prompt=system_prompt)


class ProviderRegistry:
    """Two-step provider pattern: add a ProviderSpec, then configure it."""

    def __init__(self) -> None:
        self._specs: dict[str, ProviderSpec] = {spec.name: spec for spec in self._default_specs()}

    def register(self, spec: ProviderSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> ProviderSpec:
        if name not in self._specs:
            known = ", ".join(sorted(self._specs))
            raise KeyError(f"unknown provider: {name}. known providers: {known}")
        return self._specs[name]

    def list_specs(self) -> list[ProviderSpec]:
        return [self._specs[name] for name in sorted(self._specs)]

    def create_client(self, config: AgentConfig) -> ProviderClient:
        chat_spec = self.get(config.provider)
        chat_base_url = config.base_url or chat_spec.base_url
        chat_model = config.chat_model or chat_spec.default_chat_model
        chat_embedding_model = config.embedding_model or chat_spec.default_embedding_model
        chat_api_key = config.resolved_api_key() or os.getenv(chat_spec.api_key_env)
        chat_client = self._build_single_client(
            spec=chat_spec,
            base_url=chat_base_url,
            chat_model=chat_model,
            embedding_model=chat_embedding_model,
            api_key=chat_api_key,
        )

        embedding_provider_name = (config.embedding_provider or config.provider).strip()
        embedding_spec = self.get(embedding_provider_name)
        embedding_base_url = (
            config.embedding_base_url
            or (chat_base_url if embedding_provider_name == config.provider else embedding_spec.base_url)
        )
        embedding_model = config.embedding_model or embedding_spec.default_embedding_model
        embedding_api_key = config.resolved_embedding_api_key()
        if not embedding_api_key:
            if embedding_provider_name == config.provider:
                embedding_api_key = chat_api_key
            else:
                embedding_api_key = os.getenv(embedding_spec.api_key_env)
        embedding_client = self._build_single_client(
            spec=embedding_spec,
            base_url=embedding_base_url,
            chat_model=embedding_spec.default_chat_model,
            embedding_model=embedding_model,
            api_key=embedding_api_key,
        )

        if (
            embedding_provider_name == config.provider
            and embedding_base_url == chat_base_url
            and embedding_api_key == chat_api_key
        ):
            return chat_client
        return SplitProviderClient(chat_client=chat_client, embedding_client=embedding_client)

    @staticmethod
    def _build_single_client(
        *,
        spec: ProviderSpec,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        api_key: str | None,
    ) -> ProviderClient:
        if not api_key:
            return LocalHeuristicClient()
        if spec.api_style == "anthropic":
            return AnthropicClient(base_url=base_url, api_key=api_key, chat_model=chat_model)
        return OpenAICompatibleClient(
            base_url=base_url,
            api_key=api_key,
            chat_model=chat_model,
            embedding_model=embedding_model,
        )

    @staticmethod
    def _default_specs() -> list[ProviderSpec]:
        return [
            ProviderSpec(
                name="openrouter",
                base_url="https://openrouter.ai/api/v1",
                default_chat_model="openai/gpt-4o-mini",
                default_embedding_model="text-embedding-3-small",
                api_key_env="OPENROUTER_API_KEY",
                notes="Access multiple model families.",
            ),
            ProviderSpec(
                name="anthropic",
                base_url="https://api.anthropic.com/v1",
                default_chat_model="claude-3-5-sonnet-latest",
                default_embedding_model="text-embedding-3-small",
                api_key_env="ANTHROPIC_API_KEY",
                api_style="anthropic",
                notes="Direct Anthropic API; embeddings may require fallback.",
            ),
            ProviderSpec(
                name="openai",
                base_url="https://api.openai.com/v1",
                default_chat_model="gpt-4o-mini",
                default_embedding_model="text-embedding-3-small",
                api_key_env="OPENAI_API_KEY",
                notes="Direct OpenAI API.",
            ),
            ProviderSpec(
                name="deepseek",
                base_url="https://api.deepseek.com/v1",
                default_chat_model="deepseek-chat",
                default_embedding_model="text-embedding-3-small",
                api_key_env="DEEPSEEK_API_KEY",
                notes="DeepSeek-compatible endpoint.",
            ),
            ProviderSpec(
                name="groq",
                base_url="https://api.groq.com/openai/v1",
                default_chat_model="llama-3.3-70b-versatile",
                default_embedding_model="text-embedding-3-small",
                api_key_env="GROQ_API_KEY",
                notes="Groq OpenAI-compatible endpoint.",
            ),
            ProviderSpec(
                name="gemini",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                default_chat_model="gemini-1.5-flash",
                default_embedding_model="text-embedding-3-small",
                api_key_env="GEMINI_API_KEY",
                notes="Gemini OpenAI-compatible surface.",
            ),
            ProviderSpec(
                name="vllm",
                base_url="http://localhost:8000/v1",
                default_chat_model="local-model",
                default_embedding_model="local-embedding-model",
                api_key_env="VLLM_API_KEY",
                notes="Any local OpenAI-compatible server.",
            ),
            ProviderSpec(
                name="custom",
                base_url="http://localhost:8000/v1",
                default_chat_model="custom-chat-model",
                default_embedding_model="custom-embedding-model",
                api_key_env="CUSTOM_API_KEY",
                notes="Custom OpenAI-compatible endpoint.",
            ),
        ]


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        chat_model: str,
        embedding_model: str,
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.timeout_seconds = timeout_seconds
        self._fallback = LocalHeuristicClient()

    def embed(self, text: str) -> np.ndarray:
        payload = {"model": self.embedding_model, "input": text}
        data = self._request("/embeddings", payload)
        try:
            embedding = data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("embedding response missing data[0].embedding") from exc
        return np.asarray(embedding, dtype=np.float32)

    def score_tools(self, message: str, tool_docs: dict[str, str]) -> dict[str, float]:
        if not tool_docs:
            return {}

        tool_lines = "\n".join(f"- {name}: {doc}" for name, doc in tool_docs.items())
        prompt = (
            "Score each tool from 0 to 1 for how useful it is for the user request. "
            "Return JSON object only, keys must be tool names, values numbers.\n\n"
            f"User request:\n{message}\n\n"
            f"Tools:\n{tool_lines}"
        )
        raw = self.chat(prompt, system_prompt="You are a routing model. Return strict JSON only.")
        parsed = _parse_json_object(raw)

        scores: dict[str, float] = {}
        for name in tool_docs:
            value = parsed.get(name, 0.0)
            try:
                scores[name] = float(value)
            except (TypeError, ValueError):
                scores[name] = 0.0
        if not any(scores.values()):
            return self._fallback.score_tools(message, tool_docs)
        return scores

    def plan_tool_args(self, message: str, tool_name: str, tool_doc: str) -> dict[str, Any]:
        prompt = (
            "Produce JSON arguments for this tool call. Return JSON object only.\n\n"
            f"Tool: {tool_name}\n"
            f"Description: {tool_doc}\n"
            f"User request: {message}"
        )
        raw = self.chat(prompt, system_prompt="Return strict JSON object only.")
        parsed = _parse_json_object(raw)
        if isinstance(parsed, dict):
            return parsed
        return {"query": message}

    def synthesize_response(self, user_message: str, tool_name: str, tool_result: str, memories: list[str]) -> str:
        memory_block = "\n".join(f"- {m}" for m in memories) if memories else "(none)"
        prompt = (
            f"User message:\n{user_message}\n\n"
            f"Selected tool: {tool_name}\n"
            f"Tool result:\n{tool_result}\n\n"
            f"Relevant memories:\n{memory_block}\n\n"
            "Write a concise helpful answer for the user."
        )
        return self.chat(prompt, system_prompt="You are a helpful assistant.")

    def chat(self, user_prompt: str, *, system_prompt: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        payload = {"model": self.chat_model, "messages": messages, "temperature": 0.1}

        data = self._request("/chat/completions", payload)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("chat response missing choices[0].message.content") from exc
        return _coerce_text(content)

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("User-Agent", "picoagent/0.2.0")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                text = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            payload_text = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"provider HTTP {exc.code}: {payload_text}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"provider request failed: {exc}") from exc

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError("provider returned invalid JSON") from exc


class AnthropicClient:
    """Anthropic messages API client with local fallback embeddings."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        chat_model: str,
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.chat_model = chat_model
        self.timeout_seconds = timeout_seconds
        self._fallback = LocalHeuristicClient()

    def embed(self, text: str) -> np.ndarray:
        return self._fallback.embed(text)

    def score_tools(self, message: str, tool_docs: dict[str, str]) -> dict[str, float]:
        if not tool_docs:
            return {}
        tool_lines = "\n".join(f"- {name}: {doc}" for name, doc in tool_docs.items())
        prompt = (
            "Score each tool from 0 to 1 for how useful it is for the user request. "
            "Return JSON object only, keys must be tool names, values numbers.\n\n"
            f"User request:\n{message}\n\n"
            f"Tools:\n{tool_lines}"
        )
        raw = self.chat(prompt, system_prompt="You are a routing model. Return strict JSON only.")
        parsed = _parse_json_object(raw)

        scores: dict[str, float] = {}
        for name in tool_docs:
            value = parsed.get(name, 0.0)
            try:
                scores[name] = float(value)
            except (TypeError, ValueError):
                scores[name] = 0.0
        if not any(scores.values()):
            return self._fallback.score_tools(message, tool_docs)
        return scores

    def plan_tool_args(self, message: str, tool_name: str, tool_doc: str) -> dict[str, Any]:
        prompt = (
            "Produce JSON arguments for this tool call. Return JSON object only.\n\n"
            f"Tool: {tool_name}\n"
            f"Description: {tool_doc}\n"
            f"User request: {message}"
        )
        raw = self.chat(prompt, system_prompt="Return strict JSON object only.")
        parsed = _parse_json_object(raw)
        if parsed:
            return parsed
        return self._fallback.plan_tool_args(message, tool_name, tool_doc)

    def synthesize_response(self, user_message: str, tool_name: str, tool_result: str, memories: list[str]) -> str:
        memory_block = "\n".join(f"- {m}" for m in memories) if memories else "(none)"
        prompt = (
            f"User message:\n{user_message}\n\n"
            f"Selected tool: {tool_name}\n"
            f"Tool result:\n{tool_result}\n\n"
            f"Relevant memories:\n{memory_block}\n\n"
            "Write a concise helpful answer for the user."
        )
        return self.chat(prompt, system_prompt="You are a helpful assistant.")

    def chat(self, user_prompt: str, *, system_prompt: str | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "max_tokens": 800,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt
        data = self._request("/messages", payload)
        try:
            content = data["content"]
            if isinstance(content, list) and content:
                return str(content[0].get("text", "")).strip()
            return str(content).strip()
        except (KeyError, TypeError, AttributeError) as exc:
            raise ProviderError("anthropic response missing content") from exc

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("x-api-key", self.api_key)
        req.add_header("anthropic-version", "2023-06-01")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                text = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            payload_text = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"provider HTTP {exc.code}: {payload_text}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"provider request failed: {exc}") from exc

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError("provider returned invalid JSON") from exc


class LocalHeuristicClient:
    """Offline fallback for local development without API keys."""

    _dim = 256

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()):
            vec[hash(token) % self._dim] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def score_tools(self, message: str, tool_docs: dict[str, str]) -> dict[str, float]:
        if not tool_docs:
            return {}

        text = message.lower()
        scores: dict[str, float] = {name: 0.1 for name in tool_docs}

        for name in tool_docs:
            lname = name.lower()
            if "search" in lname and any(k in text for k in ("search", "find", "web", "lookup", "google")):
                scores[name] += 1.5
            if "file" in lname and any(k in text for k in ("file", "read", "write", "folder", "path", ".py", ".md")):
                scores[name] += 1.5
            if "shell" in lname and any(k in text for k in ("run", "command", "terminal", "ls", "cat", "grep")):
                scores[name] += 1.5

        if not any(scores.values()):
            return {name: 1.0 for name in tool_docs}
        return scores

    def plan_tool_args(self, message: str, tool_name: str, tool_doc: str) -> dict[str, Any]:
        text = message.strip()
        name = tool_name.lower()

        if "search" in name:
            return {"query": text}

        if "shell" in name:
            cleaned = text.removeprefix("run ").removeprefix("command ").strip()
            return {"command": cleaned or text}

        if "file" in name:
            read_match = re.search(r"\bread\b\s+([^\s]+)", text, flags=re.IGNORECASE)
            if read_match:
                return {"action": "read", "path": read_match.group(1)}
            write_match = re.search(r"\bwrite\b\s+([^\s]+)\s*:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
            if write_match:
                return {"action": "write", "path": write_match.group(1), "content": write_match.group(2)}
            return {"action": "read", "path": text}

        return {"query": text}

    def synthesize_response(self, user_message: str, tool_name: str, tool_result: str, memories: list[str]) -> str:
        lines = [f"Tool `{tool_name}` finished."]
        if memories:
            lines.append(f"Using {len(memories)} relevant memory items.")
        lines.append(tool_result.strip() or "No output.")
        return "\n".join(lines)

    def chat(self, user_prompt: str, *, system_prompt: str | None = None) -> str:
        text = user_prompt.strip()
        if system_prompt:
            return f"{system_prompt}\n\n{text}"[:1200]
        return text[:1200]


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}

    return {}
