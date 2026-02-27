# Picoagent Architecture & Concept Lab

## 1) Executive Summary

`picoagent` is an async, tool-using agent runtime focused on correctness and controllability rather than feature sprawl.

For the goals we set (better memory relevance, better tool confidence, simpler runtime, fewer dependencies), `picoagent` is better than nanobot because it introduces measurable decision-quality mechanisms while keeping the codebase smaller and easier to reason about.

## 2) Current Infra (What Exists Today)

### 2.1 Core Runtime

- Entry and orchestration: `picoagent/cli.py`
- Main turn engine: `picoagent/agent/loop.py`
- Async message bus: `picoagent/bus.py`
- Configuration: `picoagent/config.py`

### 2.2 Intelligence Layer

- Vector memory with cosine + decay: `picoagent/core/memory.py`
- Entropy-gated tool selection: `picoagent/core/scheduler.py`
- Adaptive threshold tuning (online): `picoagent/core/adaptive.py`
- Context builder with cache-stable system prompt and separate runtime metadata: `picoagent/agent/context.py`

### 2.3 Session & Consolidation Layer

- Persistent sessions and offset-safe consolidation state: `picoagent/session.py`
- Session-aware loop integration and memory summarization trigger: `picoagent/agent/loop.py`

### 2.4 Tooling Layer

- Typed registry and results: `picoagent/agent/tools/registry.py`
- Built-in tools: shell/search/file
- JSON-schema-like parameter validation before execution (ported from nanobot pattern)
- Workspace path boundary enforcement in file tool

### 2.5 Skills Layer (nanobot-style Markdown)

- Markdown skill loader: `picoagent/skills/markdown.py`
- Skills are loaded from: `skills/<skill-name>/SKILL.md`
- Active skills are selected by explicit mention (`$skill-name` / name match) plus description keyword match
- Skill packs can be imported with: `picoagent import-skills --source <nanobot-skills-dir>`

### 2.6 Subagent Layer

- Confidence-gated second-opinion subagent: `picoagent/agent/subagents.py`

### 2.7 Provider Layer

- Registry pattern + provider metadata: `picoagent/providers/registry.py`
- OpenAI-compatible client, Anthropic client, local heuristic fallback

### 2.8 MCP Layer

- MCP stdio server for tool listing/calling: `picoagent/mcp.py`
- MCP client wrappers for external servers: `picoagent/mcp_client.py`
- CLI command: `picoagent mcp`
- External MCP tools are auto-registered as `mcp_<server>_<tool>` when configured in `mcp_servers`
- External MCP client sessions are persistent per server process and reused across calls

### 2.9 Scheduling Layer

- Interval cron service: `picoagent/cron.py`
- Heartbeat periodic trigger: `picoagent/heartbeat.py`

### 2.10 Channel Layer

- CLI, Telegram, Discord, Slack, WhatsApp, Email adapters in `picoagent/channels/`
- Telegram/Discord support polling and reply behavior
- Discord includes message chunking and rate-limit retry handling

### 2.11 Testing & Quality

- Focused tests for memory/scheduler/skills/config/channels/session/MCP/tool-validation under `tests/`
- Compile validation already used: `python3 -m compileall -q picoagent tests`

## 3) Operational Data Flow

1. Inbound user message arrives from a channel.
2. Session is loaded/updated (`session.py`).
3. Query embedding is generated.
4. Top-k relevant memories are recalled using cosine similarity + time decay.
5. Context is assembled with stable system prompt + separate runtime metadata.
6. Skills are scored first; high-confidence skill can short-circuit tool routing.
7. Otherwise tools are scored and entropy is computed.
8. If entropy is high, agent asks for clarification.
9. If entropy is low, selected tool executes with validated arguments.
10. Result is stored to memory and adaptive threshold state is updated.
11. Optional subagent second-opinion is appended when confidence is high enough.
12. Assistant response is returned; session is persisted with offset-safe consolidation state.

## 4) Why We Are Better Than nanobot (for our design objective)

## 4.1 Better Decision Quality

- nanobot baseline relies heavily on direct LLM routing heuristics.
- picoagent adds explicit uncertainty control:
  - Shannon entropy gating for tool selection.
  - Adaptive threshold tuning from observed outcomes.
- Result: fewer blind tool calls and clearer clarify-vs-act behavior.

## 4.2 Better Memory Relevance

- nanobot memory is markdown/history oriented with consolidation workflows.
- picoagent adds vector recall with ranking and decay.
- Result: memory retrieval is relevance-based and bounded by `top_k`, not full dump.

## 4.3 Stronger Runtime Safety at Tool Boundary

- Tool input validation (schema checks) before execution.
- Workspace escape protection for filesystem actions.
- Result: lower risk of malformed tool invocations and accidental unsafe file access.

## 4.4 Simpler Dependency Surface

- picoagent keeps runtime deps minimal (`numpy` + stdlib path for most components).
- nanobot pulls more external stacks (gateway SDKs, broader integrations).
- Result: easier local debugging and lighter deployment for the core use-case.

## 4.5 Skills Compatibility Advantage

- nanobot uses markdown skill files.
- picoagent now uses the same markdown skill style (`SKILL.md`) and runtime selection behavior.
- Result: easier migration of skill packs from nanobot without rewriting in Python.

## 4.6 Better for Focused Custom Agent Builds

- picoagent architecture is optimized for a narrow, inspectable runtime.
- nanobot is broader and feature-rich, which is useful but increases complexity.
- Result: faster iteration when building a specialized internal agent.

## 5) Honest Tradeoffs (Where nanobot Is Still Strong)

nanobot is currently stronger in:

- Channel breadth and long-mature integrations.
- Richer CLI/onboarding ergonomics and templates.
- More extensive battle-tested test coverage around many production edge cases.
- MCP client-side wrappers for connecting external MCP servers (our runtime currently serves MCP; client-side connection is the next step).

## 6) Codebase Size Snapshot

- `picoagent/` code today: ~3,449 lines
- `nanobot-main/nanobot/` code: ~12,201 lines

Interpretation:
- picoagent wins on simplicity and inspectability.
- nanobot wins on breadth.

## 7) Conclusion

For the target we chose (math-backed memory + confidence routing + minimal, controllable architecture with nanobot-style skills), picoagent is better than nanobot today.

If the primary goal shifts to maximum ecosystem breadth and prebuilt integrations, nanobot still has advantages.

This means picoagent is currently the stronger foundation for a focused, high-signal agent platform, while nanobot remains a stronger general-purpose integration platform.
