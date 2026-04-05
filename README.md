# AgenArc

Directed-graph Agent Orchestration Engine with protocol-execution-visualization decoupling.

```
声明式协议 + 模板语法 + 黑板架构 + 自进化资产
```

## Core Philosophy

**"Mechanism and Strategy Separation"**

- **Kernel**: Ultra-stable, only responsible for secure scheduling and resource validation
- **Self-repair/Evolution**: Built by users within the graph flow
- **Asset Boundary**: `arc://` virtual protocol isolation

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AgenArc                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │   Protocol   │  │   Engine     │  │    Visualization    │   │
│  │    (DSL)     │  │  (Runtime)   │  │      (Future)       │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│  JSON Schema     Execution Engine     React Canvas IDE           │
│  + Template      + Scheduler          (Coming Soon)              │
│  + Conditions    + StateManager                                 │
│                  + CheckpointManager                            │
│                  + PluginManager                                 │
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

### Stage 3: Self-Evolution System (Planned)

- .arc Bundle format
- VFS (arc:// protocol mapping)
- Asset_Reader / Asset_Writer operators
- Runtime_Reload hot reload
- Schema + AST sanitizer dual validation chain

### Stage 4: Plugin System (Planned)

- Hot_Plugin_Loader
- Python/C++/External loaders
- Plugin development docs

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

### Run a Protocol

```bash
agenarc run protocol.json
```

### CLI Commands

```bash
# Run a protocol
agenarc run flow.json --input '{"key": "value"}' --mode async

# Validate a protocol
agenarc validate flow.json

# Show protocol info
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

## Protocol Example

```json
{
  "version": "1.0.0",
  "entryPoint": "trigger_1",
  "metadata": {
    "name": "example_agent",
    "description": "Example AgenArc agent"
  },
  "nodes": [
    {
      "id": "trigger_1",
      "type": "Trigger",
      "label": "Start"
    },
    {
      "id": "router_1",
      "type": "Router",
      "label": "Route Decision",
      "config": {
        "conditions": [
          {"ref": "input", "operator": "eq", "value": "go", "output": "A"}
        ],
        "default": "B"
      }
    },
    {
      "id": "log_a",
      "type": "Log",
      "label": "Log A"
    },
    {
      "id": "log_b",
      "type": "Log",
      "label": "Log B"
    }
  ],
  "edges": [
    {"source": "trigger_1", "target": "router_1"},
    {"source": "router_1", "sourcePort": "output_A", "target": "log_a"},
    {"source": "router_1", "sourcePort": "output_B", "target": "log_b"}
  ]
}
```

## Configuration

AgenArc uses YAML configuration for API keys and settings:

```yaml
# config.yaml
openai:
  api_key: your-api-key
  base_url: https://api.openai.com/v1
  default_model: gpt-4
  default_temperature: 0.7

anthropic:
  api_key: your-anthropic-key
  default_model: claude-3-sonnet-20240229

agent:
  checkpoint_dir: ~/.agenarc/checkpoints
  storage_dir: ~/.agenarc/storage
```

Environment variables override config file:

- `AGENARC_OPENAI_API_KEY`
- `AGENARC_ANTHROPIC_API_KEY`
- `AGENARC_OPENAI_MODEL`
- `AGENARC_OPENAI_BASE_URL`
- `AGENARC_CHECKPOINT_DIR`

## Development

### Project Structure

```
agenarc/
├── protocol/          # Protocol layer (JSON Schema)
├── engine/           # Execution layer
│   ├── executor.py   # Core engine
│   ├── state.py     # State management + CheckpointManager
│   ├── evaluator.py # AST safe expression evaluator
│   └── scheduler.py # Scheduling strategies
├── operators/        # Built-in operators
│   ├── builtin.py   # Core operators
│   ├── router.py    # Router operator
│   ├── loop.py      # Loop_Control operator
│   └── llm.py       # LLM operators
├── plugins/         # Plugin system
├── graph/           # Graph data structures
├── vfs/             # Virtual filesystem (arc://)
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
======================== 317 passed ========================
Coverage: 82%
```

## Roadmap

| Phase | Features | Status |
|-------|----------|--------|
| v0.1 | MVP Engine | Complete |
| v0.2 | Complete Execution Engine | Complete |
| v0.3 | Self-Evolution System | Planned |
| v0.4 | Plugin System | Planned |
| v0.5 | Visualization Platform | Planned |

## License

MIT
