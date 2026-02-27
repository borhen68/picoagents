# picoagent

`picoagent` is a fast, lightweight, and highly controllable async Python agent runtime. 

Unlike massive frameworks that rely purely on LLM heuristics to make dangerous decisions, `picoagent` focuses on **safety, correctness, and mathematical routing**. It is designed to be the perfect foundation for building focused, high-signal agent workflows that you can actually trust on your local machine.

## ✨ Key Features
- **Entropy-Gated Tool Selection**: Uses TF-IDF and Shannon Entropy to calculate math-backed confidence scores *before* tools execute. If the agent is unsure, it is forced to ask you for clarification instead of hallucinating a command.
- **Dual-Layer Memory**: Combines Vector embeddings (cosine-similarity + time decay) with an automated background LLM consolidation process. Long conversations are seamlessly summarized into a `HISTORY.md` log and a permanent `MEMORY.md` context file.
- **Strict Workspace Sandboxing**: The built-in `ShellTool` and `FileTool` are locked to your designated workspace directory by default. Dangerous regex patterns (`rm -rf`, disk formats, fork bombs) and path traversing (`../../`) are actively blocked.
- **Markdown Templates & Skills**: Fully compatible with nanobot-style `SKILL.md` folders and `SOUL.md`/`USER.md` templates. Control your agent's personality and capabilities using plain English markdown files.
- **Broad Channel Support**: Native gateway adapters for CLI, Telegram, Discord, Slack, WhatsApp, and Email.

## 🚀 Quick Start

### 1. Install
```bash
git clone https://github.com/borhen68/picoagents.git
cd picoagents
pip install -e .
```

### 2. Configure
Initialize your configuration and API keys:
```bash
picoagent onboard
```

### 3. Run
Start chatting in your terminal:
```bash
picoagent agent
```
Or start the gateway to connect to Telegram, Discord, etc.:
```bash
picoagent gateway
```

## 🛠 Commands

- `picoagent onboard`: Create your initial config and setup required directories.
- `picoagent agent`: Start an interactive CLI chat session.
- `picoagent gateway`: Start all configured external channel adapters (Telegram, Slack, etc.).
- `picoagent providers`: List all registered LLM provider specs.
- `picoagent tools`: List all enabled tools currently available to the agent.
- `picoagent import-skills --source <dir>`: Import nanobot-style `SKILL.md` folders into your workspace.

## 🧠 Why Picoagent?

If you want a massive general-purpose integration platform with hundreds of pre-built integrations, use heavier frameworks. 

If your goal is **maximum inspectability, minimal dependencies, and strict runtime safety**, `picoagent` is the superior choice. 

By enforcing tool input validation, workspace escape protection, and entropy-gated execution, `picoagent` guarantees a lower risk of malformed AI invocations ruining your local environment.

## 📡 Gateway Channels

Supported external channels:
- `cli`
- `telegram` (Bot API polling)
- `discord` (REST polling for a channel)
- `slack`
- `whatsapp`
- `email`

You can enable these by editing your generated `config.json` and adding your respective Bot Tokens.

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

## 📄 License
MIT
