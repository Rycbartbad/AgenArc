# AgenArc

Directed-graph Agent Orchestration Engine with protocol-execution-visualization decoupling.

## Core Philosophy

**"Mechanism and Strategy Separation"**

- **Kernel**: Ultra-stable, only responsible for secure scheduling and resource validation
- **Self-repair/Evolution**: Built by users within the graph flow
- **Asset Boundary**: `agrc://` virtual protocol isolation

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AgenArc                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │   Protocol   │  │   Engine     │  │    Visualization    │   │
│  │    (DSL)    │  │  (Runtime)   │  │      (Future)      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│  JSON Schema       Execution Engine       React Canvas IDE        │
│  + Template        + Scheduler           (Coming Soon)           │
│  + Conditions      + StateManager                                │
│                     + CheckpointManager                          │
│                     + PluginManager                              │
└─────────────────────────────────────────────────────────────────┘
```

## Features

### Stage 1: MVP Engine (Complete)

- JSON Schema protocol definition
- ExecutionEngine core with linear flow
- Built-in operators: Trigger, Memory_I/O, Script_Node, Log, Context_Set, Context_Get
- CLI: `agenarc run <protocol.json>`

### Stage 2: Complete Execution Engine (Complete)

- **Router** - Conditional branching (if-else, switch-case)
- **Loop_Control** - Loop iteration with accumulation
- **Script_Node** - Custom scripts with AST safety
- **CheckpointManager** - File-based persistence for interruption recovery
- **AST Evaluator** - Safe expression evaluation

### Stage 3: Self-Evolution System (Complete)

- **.agrc Bundle format** - Self-contained agent package
- **VFS** - `agrc://` protocol mapping for secure file access
- **Asset_Reader** - Read files from bundle via VFS
- **Asset_Writer** - Write files with atomic operations
- **Runtime_Reload** - Hot reload scripts and plugins
- Schema + AST sanitizer dual validation chain

### Stage 4: Plugin System (Complete)

- **Hot_Plugin_Loader** - File watching + atomic reload + zero-downtime
- **Python/C++/External loaders** - Multi-language plugin support
- **Plugin development docs**

### Stage 5: Visualization Platform (Planned)

- React + TypeScript Canvas
- Node drag-and-drop
- Property editor panel
- Execution preview and debugging

## Quick Start

### Installation

```bash
pip install agenarc
```

### Run an Agent

```bash
# Run an .agrc agent bundle
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/chat_agent.agrc --input '{"trigger_payload":"Hello"}'
```

## Examples

Located in `examples/` directory:

| Agent | Description |
|-------|-------------|
| `hello_agent.agrc` | Minimal example (Trigger + Log) |
| `chat_agent.agrc` | Basic LLM chat (Trigger + LLM_Task + Log) |
| `router_agent.agrc` | Conditional routing (Trigger + LLM_Task + Router + Log) |
| `full_agent.agrc` | Complete features with manifest and scripts |

### Running Examples

```bash
# Hello Agent (no LLM needed)
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/hello_agent.agrc --input '{}'

# Chat Agent (requires LLM)
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/chat_agent.agrc --input '{"trigger_payload":"Hello!"}'

# Router Agent
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/router_agent.agrc --input '{"trigger_payload":"Say hello"}'

# Full Agent
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/full_agent.agrc --input '{"trigger_payload":"What is AI?"}'
```

## CLI Commands

```bash
# Run an agent (.agrc) or protocol (.json)
agenarc run my_agent.agrc
agenarc run flow.json --input '{"key": "value"}' --mode async

# Interactive shell (REPL mode)
agenarc shell my_agent.agrc

# Validate an agent or protocol
agenarc validate my_agent.agrc
agenarc validate flow.json

# Show agent/protocol info
agenarc info my_agent.agrc
agenarc info flow.json
```

## Node Types

| Type | Description |
|------|-------------|
| `Trigger` | Entry point for graph execution |
| `LLM_Task` | Execute LLM inference |
| `Router` | Conditional branching |
| `Loop_Control` | Loop iteration control |
| `Memory_I/O` | Read/write to persistent storage |
| `Script_Node` | Execute inline Python scripts |
| `Log` | Log and pass through values |
| `Context_Set` | Set values in global context |
| `Context_Get` | Get values from global context |

## .agrc Bundle Structure

```
my_agent.agrc/
├── manifest.json      # Agent metadata
├── flow.json         # Workflow definition
├── prompts/          # Prompt templates
│   └── system.pt     # System prompt
├── scripts/          # Custom scripts (optional)
│   └── tool.py
└── assets/           # Static assets (optional)
```

### manifest.json

```json
{
  "name": "my_agent",
  "version": "1.0.0",
  "entry": "flow.json",
  "permissions": {
    "allow_script_read": true,
    "allow_script_write": true,
    "allow_prompt_read": true
  },
  "immutable_nodes": ["trigger_1"],
  "hot_reload": true
}
```

### flow.json

```json
{
  "version": "1.0.0",
  "entryPoint": "trigger_1",
  "nodes": [
    {"id": "trigger_1", "type": "Trigger", "label": "Start"},
    {
      "id": "llm_1",
      "type": "LLM_Task",
      "label": "Chat",
      "config": {
        "model": "deepseek-chat",
        "system_prompt": "agrc://prompts/system.pt"
      }
    },
    {"id": "log_1", "type": "Log", "label": "Output"}
  ],
  "edges": [
    {"source": "trigger_1", "sourcePort": "payload", "target": "llm_1", "targetPort": "prompt"},
    {"source": "llm_1", "sourcePort": "response", "target": "log_1", "targetPort": "message"}
  ]
}
```

## Configuration

AgenArc uses YAML configuration for API keys and settings:

```yaml
# config.yaml
openai:
  api_key: your-api-key
  base_url: https://api.deepseek.com
  default_model: deepseek-chat
  temperature: 0.7
```

**Supported API endpoints:**

| Provider | base_url |
|----------|----------|
| DeepSeek | `https://api.deepseek.com` |
| OpenAI | `https://api.openai.com/v1` |
| Ollama (local) | `http://localhost:11434/v1` |

Environment variables override config file:

- `AGENARC_OPENAI_API_KEY`
- `AGENARC_OPENAI_BASE_URL`
- `AGENARC_OPENAI_MODEL`

## Development

### Project Structure

```
agenarc/
├── protocol/          # Protocol layer (JSON Schema)
├── engine/           # Execution layer
│   ├── executor.py   # Core engine
│   ├── state.py     # State management + CheckpointManager
│   └── evaluator.py # AST safe expression evaluator
├── operators/        # Built-in operators
│   ├── builtin.py   # Core operators
│   ├── router.py    # Router operator
│   ├── loop.py      # Loop_Control operator
│   └── llm.py      # LLM operators
├── vfs/             # Virtual filesystem (agrc://)
├── plugins/         # Plugin system
├── graph/           # Graph data structures
└── cli/             # Command-line interface
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=agenarc --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_builtin_operators.py -v
```

### Current Test Status

```
======================== 619 passed ========================
Coverage: 79%
```

## Roadmap

| Phase | Features | Status |
|-------|----------|--------|
| v0.1 | MVP Engine | Complete |
| v0.2 | Complete Execution Engine | Complete |
| v0.3 | Self-Evolution System | Complete |
| v0.4 | Plugin System | Complete |
| v0.5 | Visualization Platform | Planned |

## License

MIT
