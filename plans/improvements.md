# Picoagent Improvement Plan

After a thorough review of the entire codebase, here are the improvements organized by category and priority.

---

## 1. Bugs & Correctness Issues

### 1.1 `cmd_onboard` writes to non-existent attributes (cli.py:253-273)
The `cmd_onboard` function sets attributes like `cfg.provider`, `cfg.chat_model`, `cfg.api_key`, and `cfg.enabled_channels` directly on `AgentConfig`, but these are **read-only properties** or don't exist as settable fields. For example:
- `cfg.provider` is a `@property` that delegates to `cfg.agents.provider` — assigning to it silently creates a new instance attribute that shadows the property.
- `cfg.chat_model` is also a `@property`.
- `cfg.api_key` doesn't exist at all.
- `cfg.enabled_channels` is a `@property`.

**Fix:** Update `cmd_onboard` to write to the correct nested config objects (`cfg.agents.provider`, `cfg.agents.model`, etc.).

### 1.2 Redundant condition in `_migrate_config` (config.py:649)
```python
if not agents.get("model") and not agents.get("model"):
```
This checks the same condition twice. Should be:
```python
if not agents.get("model"):
```

### 1.3 `_maybe_consolidate_session` uses `asyncio.create_task` from sync-like context (loop.py:390)
The method `_maybe_consolidate_session` is called from `_finalize_session_turn` which is a sync method. It uses `asyncio.create_task()` which requires a running event loop. While this works because it's ultimately called from an async context (`run_turn`), the fire-and-forget task has no error handling — if it fails, the exception is silently lost.

**Fix:** Add a `done_callback` to log exceptions from the created task.

### 1.4 `allow_pickle=True` in memory loading (memory.py:137)
Using `np.load(..., allow_pickle=True)` is a known security risk. If an attacker can modify the `.npz` file, they can execute arbitrary code.

**Fix:** Store texts and metadata separately as JSON instead of pickled numpy arrays, or validate the file source.

### 1.5 Discord `_request` creates `Request` once but retries with same object (discord_.py:113-140)
The `urllib.request.Request` object is created once and reused across retry attempts. Some HTTP libraries consume the body on first use. While `urllib` handles this correctly, it's fragile.

**Fix:** Move request creation inside the retry loop.

---

## 2. Security Improvements

### 2.1 Shell command deny patterns are incomplete (shell.py:34-44)
The deny patterns miss several dangerous commands:
- `curl ... | bash` (pipe to shell)
- `wget ... | sh`
- `eval` command
- `sudo` commands
- `chmod 777` (overly permissive)
- `> /etc/` (writing to system files)
- Environment variable exfiltration (`env`, `printenv` piped to external)

**Fix:** Add additional deny patterns for common attack vectors.

### 2.2 API keys stored in plaintext JSON (config.py)
The config file stores API keys in plaintext JSON at `~/.picoagent/config.json`. While this is common for CLI tools, it should at minimum set restrictive file permissions.

**Fix:** Set `0600` permissions on the config file after writing.

### 2.3 No rate limiting on channel handlers
All channel adapters (Telegram, Discord, Slack, WhatsApp, Email) process every incoming message without rate limiting. A malicious user could flood the agent with requests, causing excessive API costs.

**Fix:** Add a simple per-sender rate limiter (e.g., max N messages per minute).

### 2.4 Email channel has no sender allowlist
Unlike Telegram (which has `allow_from`), the email channel processes emails from any sender. This is a significant security concern.

**Fix:** Add an `allow_from` field to `EmailChannelConfig`.

---

## 3. Code Quality & DRY Improvements

### 3.1 Duplicated `score_tools` / `plan_tool_args` / `synthesize_response` across providers
`OpenAICompatibleClient` and `AnthropicClient` have nearly identical implementations of `score_tools`, `plan_tool_args`, and `synthesize_response`. The only difference is the underlying `chat()` method.

**Fix:** Extract a mixin or base class with shared logic, keeping only `chat()` and `embed()` as abstract.

### 3.2 Duplicated `_split_message` function
Both `telegram.py` and `discord_.py` have their own `_split_message` function with nearly identical logic.

**Fix:** Move to a shared utility module (e.g., `picoagent/channels/utils.py`).

### 3.3 `AgentLoop.run_turn` is too long (~270 lines)
The `run_turn` method handles too many concerns: session management, skill selection, tool scoring, argument planning, validation, execution, chaining, memory storage, and response synthesis.

**Fix:** Extract helper methods: `_score_and_decide()`, `_plan_and_validate_args()`, `_execute_tool_chain()`.

### 3.4 Inconsistent logging
The codebase mixes `loguru`, `logging`, and `print()` for output:
- `dual_memory.py` uses `loguru`
- `whatsapp.py` uses `logging.getLogger()`
- `hooks.py` uses `logging.getLogger()`
- `cli.py` uses `print()`
- `loop.py` imports `logging` inline

**Fix:** Standardize on `loguru` (already a dependency) throughout.

### 3.5 Missing `__all__` exports in several modules
Several `__init__.py` files are missing or have incomplete `__all__` definitions.

---

## 4. Robustness & Error Handling

### 4.1 No graceful shutdown for gateway channels
When `run_gateway` encounters an exception in one channel, it cancels all pending tasks but doesn't clean up resources (e.g., close WebSocket connections, flush sessions).

**Fix:** Add cleanup handlers and use `asyncio.TaskGroup` or proper shutdown logic.

### 4.2 Session file corruption risk (session.py:89)
`SessionManager.save()` writes directly to the session file. If the process crashes mid-write, the file will be corrupted.

**Fix:** Write to a temporary file first, then atomically rename.

### 4.3 Memory file corruption risk (memory.py:123)
Same issue as sessions — `np.savez_compressed` writes directly to the target path.

**Fix:** Write to a temp file, then rename.

### 4.4 No connection pooling for HTTP requests
All provider clients use `urllib.request.urlopen()` for each request, creating a new TCP connection every time. This adds latency.

**Fix:** Consider using `urllib3` or `httpx` for connection pooling (though this adds a dependency).

### 4.5 MCP session doesn't handle out-of-order responses (mcp_client.py:225-228)
The `_request` method reads from a shared queue and only matches by `id`. If a notification or unrelated message arrives, it's consumed and lost.

**Fix:** Re-queue non-matching messages or use a dict of pending futures.

---

## 5. Missing Tests

### 5.1 No tests for `cli.py` commands
The CLI module (`cmd_onboard`, `cmd_agent`, `cmd_gateway`, `build_agent_loop`, etc.) has zero test coverage.

### 5.2 No tests for `AgentLoop.run_turn` happy path
`test_agent_loop_fallback.py` only tests fallback scenarios. There are no tests for the main tool execution path, tool chaining, or session consolidation.

### 5.3 No tests for email channel
`EmailChannel` has no test file.

### 5.4 No tests for Slack channel
`SlackChannel` has no test file.

### 5.5 No integration test for provider clients
The `OpenAICompatibleClient` and `AnthropicClient` are not tested (even with mocked HTTP).

---

## 6. Performance Improvements

### 6.1 Tool cache has no size limit (registry.py:37)
The `ToolRegistry._cache` dict grows unbounded. Over time, this can consume significant memory.

**Fix:** Add a max cache size with LRU eviction.

### 6.2 Memory recall does full matrix multiplication every time (memory.py:88)
For large memory stores, `np.vstack` + matrix multiply on every recall is expensive.

**Fix:** Consider pre-computing the embedding matrix and updating incrementally.

### 6.3 Skill selection scans all skills on every message (skills/markdown.py)
`select_for_message` does keyword matching against all skills for every user message.

**Fix:** Build an inverted index of keywords → skills for O(1) lookup.

---

## 7. Developer Experience

### 7.1 No `py.typed` marker
The package doesn't include a `py.typed` marker file, so type checkers won't recognize it as typed.

### 7.2 No `__version__` in package
The version is only in `pyproject.toml` but not accessible programmatically.

### 7.3 Dockerfile doesn't use multi-stage build
The Dockerfile could be optimized with a multi-stage build to reduce image size.

---

## Implementation Priority

### Critical (bugs that cause incorrect behavior):
1. Fix `cmd_onboard` attribute assignments
2. Fix redundant condition in `_migrate_config`
3. Add fire-and-forget task error handling

### High (security):
4. Add shell deny patterns for `curl|bash`, `sudo`, `eval`
5. Set restrictive file permissions on config
6. Add email sender allowlist

### Medium (code quality):
7. Extract shared `_split_message` utility
8. Atomic file writes for sessions and memory
9. Add tool cache size limit
10. Standardize logging on loguru

### Low (nice-to-have):
11. Extract provider base class for DRY
12. Refactor `run_turn` into smaller methods
13. Add missing tests
14. Add `py.typed` marker
