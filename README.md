<div align="center">
  <h1>🌌 picoagent: The Mathematically-Routed AI Assistant</h1>
  <p>
    <a href="https://github.com/borhen68/picoagents"><img src="https://img.shields.io/badge/github-repo-blue" alt="GitHub"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

🐈 **picoagent** is a fast, lightweight, and highly controllable async Python agent runtime.

Unlike massive frameworks that rely purely on LLM heuristics to make dangerous decisions, `picoagent` focuses on **safety, correctness, and mathematical routing**. It is designed to be the perfect foundation for building focused, high-signal agent workflows that you can actually trust on your local machine.

## ✨ Key Features

🧮 **Entropy-Gated Tool Selection**: Uses TF-IDF and Shannon Entropy to calculate math-backed confidence scores *before* tools execute. If the agent is unsure, it asks for clarification instead of hallucinating.

🧠 **Dual-Layer Memory**: Combines Vector embeddings (cosine-similarity + time decay) with an automated background LLM consolidation process. Long conversations are seamlessly summarized into a `HISTORY.md` log and a permanent `MEMORY.md` context file.

🛡️ **Strict Workspace Sandboxing**: The built-in `ShellTool` and `FileTool` are locked to your designated workspace directory by default. Dangerous regex patterns (`rm -rf`, disk formats, fork bombs) and path traversing (`../../`) are actively blocked.

📝 **Markdown Templates & Skills**: Fully compatible with nanobot-style `SKILL.md` folders and `SOUL.md`/`USER.md` templates. Control your agent's personality and capabilities using plain English markdown files.

📱 **Broad Channel Support**: Native gateway adapters for CLI, Telegram, Discord, Slack, WhatsApp, and Email.

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

**2. Chat**

```bash
picoagent agent
```

That's it! You have a working, mathematically-routed AI assistant in 2 minutes.

## 💬 Chat Apps (Gateway Channels)

Connect picoagent to your favorite chat platform using the Gateway.

| Channel | What you need |
|---------|---------------|
| **Telegram** | Bot token from @BotFather |
| **Discord** | Bot token + Message Content intent |
| **WhatsApp** | Inbox/Outbox config |
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


## ⚙️ Configuration (LLM Providers)

`picoagent` supports flexible provider configurations.

**Groq (Chat) + OpenAI (Embeddings)** Example:

```json
{
  "provider": "groq",
  "chat_model": "llama-3.3-70b-versatile",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "api_key": "your-groq-key",
  "embedding_api_key_env": "OPENAI_API_KEY"
}
```

## 🔌 External MCP Tools

`picoagent` natively supports the Model Context Protocol (MCP). You can serve its internal tool registry outwards, or run it as a client to consume external tools:

```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
      "timeout_seconds": 30
    }
  ]
}
```

At startup, picoagent fetches `tools/list` from each configured server and auto-registers wrappers named `mcp_<server>_<tool>`.

## 🖥️ CLI Reference

| Command | Description |
|---------|-------------|
| `picoagent onboard` | Create `~/.picoagent/config.json` |
| `picoagent agent` | Start interactive CLI chat |
| `picoagent gateway` | Start configured channel adapters |
| `picoagent providers` | List registered provider specs |
| `picoagent tools` | List enabled tools |
| `picoagent mcp` | Run a stdio MCP server exposing the tool registry |
| `picoagent import-skills --source <dir>` | Import nanobot-style `SKILL.md` folders |

## 🧠 Why Picoagent? (vs nanobot)

If you want a massive general-purpose integration platform with hundreds of pre-built integrations, nanobot is a fantastic choice.

If your goal is **maximum inspectability, minimal dependencies, and strict runtime safety**, `picoagent` is the superior choice.

By enforcing tool input validation, workspace escape protection, and entropy-gated execution, `picoagent` guarantees a lower risk of malformed AI invocations ruining your local environment.

## 📄 License
MIT
