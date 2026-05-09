# AgenArc

<div align="center">

**Directed-Graph Agent Orchestration Engine**

[![PyPI - Version](https://img.shields.io/pypi/v/agenarc?color=blue)](https://pypi.org/project/agenarc/)
[![Python](https://img.shields.io/pypi/pyversions/agenarc)](https://pypi.org/project/agenarc/)
[![License](https://img.shields.io/github/license/Rycbartbad/AgenArc)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-742%20passed-brightgreen)](https://github.com/Rycbartbad/AgenArc)
[![Coverage](https://img.shields.io/badge/coverage-62%25-yellow)](https://github.com/Rycbartbad/AgenArc)

</div>

---

## Philosophy

> **"Mechanism and Strategy Separation"**

| Layer | Role |
|-------|------|
| **Kernel** | Ultra-stable scheduler — secure execution, resource validation, VFS sandbox |
| **Self-repair** | Built by users within the graph flow — evolve agents without touching the engine |
| **Asset boundary** | `agrc://` virtual protocol — files, scripts, and prompts live in isolated bundles |

---

## Architecture

```
 ┌──────────────────────────────────────────────────────────┐
 │                      AgenArc v0.5                        │
 ├──────────────────────────────────────────────────────────┤
 │                                                           │
 │  ┌──────────┐    ┌──────────┐    ┌──────────────────┐    │
 │  │ Protocol │───▶│  Engine  │───▶│  Visualization   │    │
 │  │   (DSL)  │    │ (Runtime)│    │   (Web IDE)      │    │
 │  └──────────┘    └──────────┘    └──────────────────┘    │
 │        │               │                  │               │
 │  ┌─────▼─────┐  ┌──────▼──────┐  ┌───────▼────────┐     │
 │  │JSON Schema│  │  Scheduler  │  │  Graph Editor   │     │
 │  │+ Templates│  │  + Router   │  │  + Live Preview │     │
 │  │+ Conditions│ │  + Join     │  │  + Context Panel│     │
 │  └───────────┘  │  + Checkpoint│ │  + Status LEDs  │     │
 │                 │  + Plugins   │  └────────────────┘     │
 │                 └─────────────┘                          │
 └──────────────────────────────────────────────────────────┘
```

---

## Features

| Category | Highlights |
|----------|-----------|
| **Execution** | Linear & parallel & async modes, Router (conditional branching), Join (branch sync), CheckpointManager |
| **LLM** | Streaming responses, multi-provider fallback, structured error classification |
| **Scripting** | `Script_Node` with AST-safe evaluator (3 trust levels), gas & memory limits |
| **Packaging** | `.agrc` self-contained bundles — JSON protocol + prompts + scripts + plugins in one ZIP |
| **VFS** | `agrc://` virtual filesystem with `rwx` permissions, path-traversal protection |
| **Plugins** | Python / C++ / External loaders, hot-reload (file watching), event plugins |
| **Visualization** | Web IDE — drag-and-drop graph editor, real-time execution preview, YAML context panel |
| **CLI** | `run` / `shell` / `serve` / `validate` / `info` / `pack` / `visualize` |

## Node Types

| Node | Description | Input → Output |
|------|-------------|---------------|
| `Trigger` | Entry point | `payload` → graph |
| `LLM_Task` | LLM inference (streaming + fallback) | `messages` → `response`, `usage`, `error` |
| `Router` | Conditional branching (all matches execute in parallel) | `input` → dynamic output ports |
| `Join` | Synchronize parallel branches (merge / concat / first) | dynamic → `output` |
| `Memory_I/O` | Persistent key-value storage (transactional + checkpoint) | `key`, `value` → `value`, `success` |
| `Script_Node` | Inline Python with AST safety (3 trust levels) | arbitrary → `result` |
| `Prompt_Builder` | Multi-turn conversation history management | `user` / `assistant` → `messages` |
| `Log` | Log and pass-through | `message` → `message` |
| `Context_Set` | Set global context values | `key`, `value` → `success` |
| `Context_Get` | Read global context values | `key` → `value` |
| `Asset_Reader` | Read files from bundle via VFS | `path` → `content`, `success` |
| `Asset_Writer` | Write files with atomic operations | `path`, `content` → `success` |
| `Runtime_Reload` | Hot reload scripts and plugins at runtime | `target` → `success` |

---

## Quick Start

```bash
pip install agenarc
```

```bash
# Run a chat agent
agenarc run examples/my_first_agent.agrc --input '{"payload":"Hello!"}'

# Interactive REPL
agenarc shell examples/my_first_agent.agrc

# Background service with plugins
agenarc serve examples/euchea.agrc

# Web-based graph editor
agenarc visualize examples/my_first_agent.agrc
```

### Examples

| Agent | Description |
|-------|-------------|
| `my_first_agent.agrc` | Multi-turn chat — Trigger → Prompt_Builder → LLM_Task |
| `qq_bot_agent.agrc` | QQ bot with event plugin (`serve` mode) |
| `euchea.agrc` | PDF → C++ code generation via Alt+A hotkey (`serve` mode) |

---

## .agrc Bundle

```
my_agent.agrc/
├── manifest.json          # Metadata, permissions, hot_reload
├── flow.json              # Graph definition (nodes + edges)
├── prompts/
│   └── system.pt          # {{template}} prompt files
├── scripts/
│   └── tool.py            # Custom scripts (optional)
├── plugins/                # Embedded plugins (auto-discovered)
│   └── my_plugin/
│       ├── agenarc.json
│       └── plugin.py
└── assets/                 # Static assets (optional)
```

<details>
<summary><b>Example flow.json</b></summary>

```json
{
  "version": "1.0.0",
  "nodes": [
    { "id": "trigger_1", "type": "Trigger", "label": "Start" },
    {
      "id": "llm_1",
      "type": "LLM_Task",
      "label": "Chat",
      "config": {
        "model": "deepseek-chat",
        "system_prompt": "agrc://prompts/system.pt",
        "stream": true,
        "providers": ["deepseek", "openrouter"]
      }
    },
    { "id": "log_1", "type": "Log", "label": "Output" }
  ],
  "edges": [
    { "source": "trigger_1", "sourcePort": "payload", "target": "llm_1", "targetPort": "messages" },
    { "source": "llm_1", "sourcePort": "response", "target": "log_1", "targetPort": "message" }
  ]
}
```

</details>

---

## Configuration

```yaml
# ~/.agenarc/config.yaml

providers:
  deepseek:
    api_key: sk-your-key
    base_url: https://api.deepseek.com
    default_model: deepseek-chat
    temperature: 0.7

  openrouter:
    api_key: sk-your-key
    base_url: https://openrouter.ai/api/v1
    default_model: openrouter/free

agent:
  checkpoint_dir: ~/.agenarc
```

| Provider | base_url |
|----------|----------|
| DeepSeek | `https://api.deepseek.com` |
| OpenAI | `https://api.openai.com/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| Ollama | `http://localhost:11434/v1` |

Environment variables override config: `AGENARC_OPENAI_API_KEY`, `AGENARC_OPENAI_BASE_URL`, `AGENARC_OPENAI_MODEL`, `AGENARC_ANTHROPIC_API_KEY`, `AGENARC_ANTHROPIC_MODEL`, `AGENARC_CHECKPOINT_DIR`

---

## Development

```
agenarc/
├── protocol/           # JSON Schema + protocol loader
├── engine/             # Executor, state manager, AST evaluator
├── operators/          # 13 built-in operators
├── vfs/                # agrc:// virtual filesystem
├── plugins/            # Plugin loader (Python/C++/External)
├── graph/              # Graph data structures + traversal
├── visualization/      # Web IDE server + static frontend
└── cli/                # Command-line interface
```

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/                          # All (742 passed)
pytest tests/ --cov=agenarc            # With coverage (~62%)
pytest tests/unit/test_builtin_operators.py -v  # Single file

# Lint & type check
ruff check agenarc/
ruff format --check agenarc/
mypy agenarc/
```

---

## Roadmap

| Version | Phase | Status |
|---------|-------|--------|
| v0.1 | MVP Engine | ✅ |
| v0.2 | Execution Engine — Router, Join, Checkpoint | ✅ |
| v0.3 | Self-Evolution — Bundle, VFS, Hot Reload | ✅ |
| v0.4 | Plugin System — Python / C++ / External | ✅ |
| **v0.5** | **Visualization Platform — Web IDE, Live Preview** | ✅ |

---

## Documentation

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Release history and change log |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, PR process, commit style |
| [docs/agents.md](docs/agents.md) | User-facing agent creation guide (Chinese) |
| [docs/plugins/README.md](docs/plugins/README.md) | Plugin development guide |

---

## License

MIT © [Rycbartbad](https://github.com/Rycbartbad)
