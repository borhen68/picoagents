<div align="center">
  <img src="assets/logo.png" alt="picoagent logo" width="150" style="border-radius: 20%; margin-bottom: 20px;" />
  <h1>🌌 picoagent: Ultra-Lightweight & Mathematically Routed AI</h1>
  <p>
    <a href="https://github.com/borhen68/picoagents"><img src="https://img.shields.io/badge/github-repo-blue" alt="GitHub"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

🐈 **picoagent** is an **ultra-lightweight** personal AI assistant focused on mathematical tool-routing and safety.

⚡️ Delivers advanced agent functionality (Vector embeddings, Sandboxing, Dual-Layer Memory, Tool Chains, Plugin Hooks) in just **~5,750** lines of code.

📏 Real-time line count: **5,756 lines**

## 📢 News

- **2026-02-28** 🔗 **Multi-Turn Tool Chains:** Agent can now chain up to 3 tool executions automatically without requiring new user messages. Each tool result is fed back into entropy scoring for the next tool.
- **2026-02-28** ⏱️ **Tool Timeout Protection:** Every tool execution is now wrapped with a 30-second timeout (configurable). Prevents hanging tools from blocking the agent forever.
- **2026-02-28** 🗃️ **Tool Result Caching:** Successful tool results are cached for 60 seconds, avoiding redundant API calls for repeated queries.
- **2026-02-28** 🪝 **Plugin Hook System:** New `picoagent/hooks.py` module exposes `on_turn_start`, `on_tool_result`, and `on_turn_end` events for extensibility.
- **2026-02-28** 📥 **Skill Install Command:** New `picoagent install-skill <user/repo>` command installs skills directly from GitHub.
- **2026-02-28** 🔄 **Skill Hot-Reload:** Skills can now be reloaded on-the-fly by sending SIGHUP to the running agent.
- **2026-02-28** 📊 **Skill Usage Telemetry:** Tracks which skills are used and how often in `~/.picoagent/skill_usage.jsonl`.
- **2026-02-28** 🧩 **Skill Dependencies:** Skills can now declare `requires: [other-skill]` to auto-load dependencies.
- **2026-02-27** 🛡️ **Workspace Sandboxing & Dual-Layer Memory:** Built-in `FileTool` and `ShellTool` are now safely sandboxed to your workspace. The LLM now continuously consolidates your long conversations into a searchable `HISTORY.md` and semantic `MEMORY.md` file in the background!
- **2026-02-27** 🧮 **Entropy-Gating Engine:** Agent workflow now calculates Shannon Entropy and TF-IDF scores locally before executing tools to prevent hallucinations.
- **2026-02-26** 🤖 **Template Support:** Full compatibility with nanobot-style Markdown templates (`SOUL.md`, `USER.md`).

## Key Features of picoagent:

🎯 **Multi-Turn Tool Chains**: The agent can automatically execute up to 3 tool calls in sequence, feeding each result back into entropy scoring for the next decision.

⏱️ **Tool Timeout Protection**: Every tool execution has a configurable timeout (default 30s) to prevent hanging.

🗃️ **Tool Result Caching**: Successful tool results are cached for 60 seconds to avoid redundant API calls.

🪝 **Plugin Hook System**: Extend picoagent with custom plugins via `on_turn_start`, `on_tool_result`, and `on_turn_end` hooks.

💎 **Skill Install from GitHub**: Install skills directly with `picoagent install-skill user/repo` — no manual download needed.

� **Ultra-Lightweight**: Just ~4,700 lines of core agent code — easy to audit and modify.

🔬 **Mathematically Routed**: Uses Shannon Entropy to gate tool execution. If the uncertainty is too high, the agent automatically asks you for clarification instead of guessing or causing harm.

🧠 **Dual-Layer Memory**: Combines rapid Vector embeddings (Cosine-Similarity + Time Decay) with permanent, human-editable Markdown memory logs.

⚡️ **Strict Safety Sandboxing**: Native Regex barriers prevent destructive shell commands, and file traversals are locked purely to the workspace root.

💎 **Easy-to-Use**: One-click configuration and instant background daemon connections to 6+ messaging platforms.

## 🏗️ Architecture Stack

- **Core Routing:** `LocalHeuristicClient` + `EntropyScheduler`
- **Memory Engine:** `VectorMemory` + `DualMemoryStore`
- **Session Layer:** `SessionManager` + `AgentLoop` (Asyncio)

## ✨ Use Cases

<table align="center">
  <tr align="center">
    <th><p align="center">🛡️ Secure Local Automation</p></th>
    <th><p align="center">🚀 Full-Stack Software Engineer</p></th>
    <th><p align="center">📅 Smart Daily Routine Manager</p></th>
    <th><p align="center">📚 Personal Knowledge Assistant</p></th>
  </tr>
  <tr>
    <td align="center">Sandboxed • Monitored • Auditable</td>
    <td align="center">Develop • Deploy • Scale</td>
    <td align="center">Cron Jobs • Heartbeats • Automate</td>
    <td align="center">Vector Recall • Decay • Reasoning</td>
  </tr>
</table>

## 📦 Install

**Install from source** (latest features, recommended for development)

```bash
git clone https://github.com/borhen68/picoagents.git
cd picoagents
pip install -e .
```

## 🚀 Quick Start

> [!TIP]
> Set your API key in `~/.picoagent/config.json`.

**1. Initialize**

```bash
picoagent onboard
```

**2. Configure (`~/.picoagent/config.json`)**

Add your preferred provider and API Keys (Example using Groq):
```json
{
  "provider": "groq",
  "chat_model": "llama-3.3-70b-versatile",
  "api_key": "YOUR_GROQ_KEY"
}
```

**3. Chat**

```bash
picoagent agent
```

That's it! You have a working AI assistant in 2 minutes.

## 💬 Chat Apps (Gateway)

Connect picoagent to your favorite chat platform. It supports persistent sessions across all of them!

| Channel | What you need |
|---------|---------------|
| **Telegram** | Bot token from @BotFather |
| **Discord** | Bot token + Message Content intent |
| **WhatsApp** | Inbox/Outbox config via Webhook bridge |
| **Slack** | Bot token + Channel ID |
| **Email** | IMAP/SMTP credentials |

<details>
<summary><b>Telegram</b> (Recommended)</summary>

**1. Create a bot**
- Open Telegram, search `@BotFather`
- Send `/newbot`, follow prompts
- Copy the token

**2. Configure** (`~/.picoagent/config.json`)

```json
{
  "enabled_channels": ["telegram"],
  "channel_tokens": {
    "telegram": "YOUR_BOT_TOKEN"
  },
  "channel_settings": {
    "telegram": {
      "allowed_chat_ids": ["YOUR_CHAT_ID"],
      "reply_to_message": true,
      "poll_seconds": 3
    }
  }
}
```

**3. Run**

```bash
picoagent gateway
```

</details>

<details>
<summary><b>Discord</b></summary>

**1. Configure** (`~/.picoagent/config.json`)

```json
{
  "enabled_channels": ["discord"],
  "channel_tokens": {
    "discord": "YOUR_BOT_TOKEN"
  },
  "channel_settings": {
    "discord": {
      "channel_id": "YOUR_CHANNEL_ID",
      "reply_as_reply": true,
      "poll_seconds": 3
    }
  }
}
```

**2. Run**

```bash
picoagent gateway
```

</details>

<details>
<summary><b>Slack</b></summary>

**1. Configure** (`~/.picoagent/config.json`)

```json
{
  "enabled_channels": ["slack"],
  "channel_tokens": {
    "slack": "xoxb-YOUR_BOT_TOKEN"
  },
  "channel_settings": {
    "slack": {
      "channel_id": "YOUR_CHANNEL_ID",
      "poll_seconds": 3
    }
  }
}
```

**2. Run**

```bash
picoagent gateway
```

</details>

<details>
<summary><b>Email</b></summary>

**1. Configure** (`~/.picoagent/config.json`)

```json
{
  "enabled_channels": ["email"],
  "channel_settings": {
    "email": {
      "username": "bot@example.com",
      "password": "app-password",
      "imap_host": "imap.example.com",
      "smtp_host": "smtp.example.com",
      "imap_port": 993,
      "smtp_port": 587,
      "use_tls": true
    }
  }
}
```

**2. Run**

```bash
picoagent gateway
```

</details>

## ⚙️ Configuration

Config file: `~/.picoagent/config.json`

### Providers

picoagent separates out its fast embedding providers from its chat providers. This allows you to mix and match (e.g., fast Groq Chat with high-dimension OpenAI Embeddings).

| Provider | Purpose | Get API Key |
|----------|---------|-------------|
| `custom` | Any OpenAI-compatible endpoint | — |
| `openrouter` | LLM (recommended, access to all models) | [openrouter.ai](https://openrouter.ai) |
| `anthropic` | LLM (Claude direct) | [console.anthropic.com](https://console.anthropic.com) |
| `openai` | LLM + Embeddings (GPT direct) | [platform.openai.com](https://platform.openai.com) |
| `deepseek` | LLM (DeepSeek direct) | [platform.deepseek.com](https://platform.deepseek.com) |
| `groq` | LLM (Fastest LLM) | [console.groq.com](https://console.groq.com) |
| `gemini` | LLM (Gemini direct) | [aistudio.google.com](https://aistudio.google.com) |
| `vllm` | LLM (local, any OpenAI-compatible server) | — |

<details>
<summary><b>Custom Provider (Any OpenAI-compatible API)</b></summary>

Connects directly to any OpenAI-compatible endpoint — LM Studio, llama.cpp, Together AI, Fireworks, Azure OpenAI, or any self-hosted server.

Set your configuration like so:

```json
{
  "provider": "custom",
  "base_url": "https://api.your-provider.com/v1",
  "chat_model": "your-model-name",
  "api_key": "your-api-key"
}
```

> For local servers that don't require a key, set `api_key` to any non-empty string (e.g. `"no-key"`).

</details>

<details>
<summary><b>Adding a New Provider (Developer Guide)</b></summary>

Unlike bloated frameworks that rely on large 3rd-party dependencies like `litellm`, picoagent manages its routing directly via a lightweight **Provider Registry** (`picoagent/providers/registry.py`) for maximum performance and security.

Adding a new provider takes just 1 easy step.

**Step 1.** Add a `ProviderSpec` entry to `_default_specs` in `picoagent/providers/registry.py`:

```python
ProviderSpec(
    name="myprovider",                   # config field name
    base_url="https://api.myprovider.com/v1", # endpoint
    default_chat_model="my-chat-model",  # default model
    default_embedding_model="my-embed-model", # fallback embeddings
    api_key_env="MYPROVIDER_API_KEY",    # env var mapping
)
```

That's it! picoagent will now treat `myprovider` as a native, globally accessible LLM option for all your agents.

</details>

### MCP (Model Context Protocol)

> [!TIP]
> The config format is universally compatible. You can copy MCP server configs directly from any MCP server's README.

picoagent supports MCP natively—connect external tool servers and use them as native agent tools.

Add MCP servers to your `config.json`:

```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
      "timeout_seconds": 30
    }
  ]
}
```

At startup, picoagent fetches `tools/list` from each configured server and auto-registers wrappers named `mcp_<server>_<tool>`. MCP client sessions are persistent per configured server process and reused across calls.

### Security

> [!TIP]
> For production deployments, Workspace Sandboxing is **enabled by default** in picoagent.

| Option | Default | Description |
|--------|---------|-------------|
| `allow_shell` | `true` | Toggles whether the agent can execute shell commands. |
| `allow_file_tool` | `true` | Toggles whether the agent can modify disk files. |
| `restrict_to_workspace` | `true`| Prevents path traversal out of the workspace root and blocks destructive command patterns. |
| `shell_path_append` | `""` | Specifically allows isolated custom shell commands `/usr/sbin` without polluting the global environment. |

## 🖥️ CLI Reference

| `picoagent onboard` | Create `~/.picoagent/config.json` |
| `picoagent agent` | Start interactive CLI chat |
| `picoagent gateway` | Start background gateway adapters (Telegram, Slack, etc.) |
| `picoagent providers` | List registered provider schemas |
| `picoagent tools` | List enabled tools |
| `picoagent mcp` | Run a stdio MCP server outward, exposing the tool registry |
| `picoagent import-skills --source <dir>` | Import nanobot-style `SKILL.md` folders to your workspace |
| `picoagent install-skill <user/repo>` | Install a skill directly from GitHub |

Interactive mode exits: `exit`, `quit`, or `Ctrl+D`.

<details>
<summary><b>Scheduled Tasks (Cron)</b></summary>

picoagent includes a built-in asynchronous cron manager! If your `cron.json` declares events, the daemon will wake up and execute tasks exactly at the scheduled POSIX intervals.

</details>

<details>
<summary><b>Heartbeat (Periodic Tasks)</b></summary>

picoagent will periodically trigger `heartbeat.py`. The gateway wakes up and checks `HEARTBEAT.md` in your workspace (`~/.picoagent/HEARTBEAT.md`). If the file has tasks, the agent executes them and delivers results to your most recently active chat channel!

</details>

## 🐳 Docker Deployment

You can deploy `picoagent` easily via Docker using the provided `docker-compose.yml`.

```bash
# 1. Edit your environment variables or config
cp dev.config.json ~/.picoagent/config.json

# 2. Start the gateway daemon in the background
docker compose up -d

# 3. Check the logs
docker compose logs -f
```
Your configuration and memory files will be safely persisted in `~/.picoagent` on your host machine.

## 🐧 Linux Service

Run the gateway as a systemd user service so it starts automatically and restarts on failure.

**Create the service file** at `~/.config/systemd/user/picoagent-gateway.service`:

```ini
[Unit]
Description=Picoagent Gateway
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/picoagent gateway
Restart=always
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=%h

[Install]
WantedBy=default.target
```

**Enable and start:**
```bash
systemctl --user daemon-reload
systemctl --user enable --now picoagent-gateway
```


## 📁 Project Structure

```
picoagent/
├── agent/            # 🧠 Core Agent Engine
│   ├── loop.py       #    Agent execution Loop & Entropy Math
│   ├── context.py    #    Dynamic System Prompt builder
│   ├── subagents.py  #    Subagent task execution
│   └── tools/        #    Built-in safe tools
├── core/             # 🧮 Intelligence Math Layer
│   ├── scheduler.py  #    Information Entropy routing
│   ├── memory.py     #    Vector Embeddings (NumPy)
│   ├── dual_memory.py#    LLM-powered semantic Markdown consolidation
│   └── adaptive.py   #    Dynamic Confidence threshold sliding
├── skills/           # 🎯 Markdown YAML capability loader
├── channels/         # 📱 External chat gateway integrations
├── providers/        # 🤖 LLM provider APIs
├── config.py         # ⚙️ Configuration models
├── mcp.py            # 🔌 Model Context Protocol Server
├── heartbeat.py      # 💓 Proactive wake-ups
├── cron.py           # ⏰ Standard POSIX interval executor
└── cli.py            # 🖥️ Terminal Commands
```

## 🤝 Roadmap

The codebase is engineered specifically for correctness and readability. 

- [x] **Multi-Turn Tool Chains** — Agent can chain up to 3 tools automatically.
- [x] **Tool Timeout Protection** — Prevents hanging tools from blocking the agent.
- [x] **Tool Result Caching** — 60-second TTL cache for repeated queries.
- [x] **Plugin Hook System** — Extensible via `on_turn_start`, `on_tool_result`, `on_turn_end`.
- [x] **Skill Install Command** — Install skills from GitHub with one command.
- [x] **Skill Hot-Reload** — Reload skills without restarting via SIGHUP.
- [x] **Skill Usage Telemetry** — Track which skills are used and how often.
- [x] **Skill Dependencies** — Skills can declare `requires:` for auto-loading.
- [ ] **Better Adaptive Tuning** — Enhancing the dynamic mathematical thresholds during continuous sessions.
- [ ] **Multi-modal Support** — Allow the agent to properly parse Images and Audio across channels.
- [ ] **Expanded Workspace Restrictions** — More fine-grained Docker-level sandboxing inside the `ShellTool`.

## 📄 License

MIT
