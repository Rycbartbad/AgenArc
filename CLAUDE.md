# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgenArc is a directed-graph Agent orchestration framework with "mechanism and strategy separation" philosophy:
- **Kernel**: Secure scheduling and resource validation (stable)
- **Strategy**: Self-repair/evolution built by users in graph flows
- **Boundary**: `agrc://` virtual protocol isolation for assets

## Commands

### Running Agents
```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run <agent.agrc|flow.json> --input '{"key": "value"}'
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/hello_agent.agrc --input '{}'
```

### CLI Commands
```bash
agenarc run <file> [--input JSON] [--mode sync|async|parallel]  # Execute (requires pip install)
agenarc validate <file>                                          # Validate protocol
agenarc info <file>                                              # Show agent info
# Alternative: python -m agenarc.cli run <file> [--input JSON]  # Without pip install
```

### Running Tests
```bash
pytest tests/                                    # All tests
pytest tests/ --cov=agenarc --cov-report=term-missing  # With coverage
pytest tests/unit/test_builtin_operators.py -v  # Single file
```

## Architecture

### Core Execution Flow
```
ProtocolLoader → Graph → GraphTraversal → ExecutionEngine → Operators → StateManager
```

### Key Components

| Layer | Files | Purpose |
|-------|-------|---------|
| **Protocol** | `schema.py`, `loader.py` | JSON Schema definitions + graph parsing |
| **Engine** | `executor.py`, `state.py`, `evaluator.py` | Core execution, checkpoints, AST evaluation |
| **Operators** | `operator.py`, `builtin.py`, `llm.py`, `router.py`, `loop.py`, `evolution.py` | Node type implementations |
| **VFS** | `filesystem.py` | `agrc://` virtual protocol mapping |
| **Graph** | `node.py`, `edge.py`, `traversal.py` | Graph data structures |
| **Plugins** | `manager.py`, `hot_loader.py`, `loaders/*.py` | Plugin discovery, hot reload, multi-language loaders |

### IOperator Interface
All operators implement [`operator.py:15`](agenarc/operators/operator.py#L15):
```python
class IOperator(ABC):
    name: str                           # "plugin.operator" format
    def get_input_ports() -> List[Port]
    def get_output_ports() -> List[Port]
    async def execute(inputs, context) -> Dict[str, Any]
```

### ExecutionEngine
[`executor.py:78`](agenarc/engine/executor.py#L78) - Central orchestrator that:
1. Loads graph via `ProtocolLoader`
2. Registers built-in operators
3. Executes nodes via `GraphTraversal.get_execution_order()`
4. Routes errors to global `errorNode` if configured

### Trust-Based Autonomy
[`schema.py:50-63`](agenarc/protocol/schema.py#L50-L63) - Four levels control Agent capabilities:
- `level_0`: Agent unaware of agrc://, VFS, bundle system (pure function)
- `level_1`: Can read prompts/scripts, evaluate expressions
- `level_2`: Can modify `flow.json`, trigger `Runtime_Reload`
- `level_3`: Full power including `manifest.json` and plugin installation

### State Management
[`state.py`](agenarc/engine/state.py) - `StateManager` handles:
- Global context (cross-node variables)
- Checkpoint/restore for interruption recovery
- Transactional Memory_I/O with rollback

### VFS (Virtual File System)
[`filesystem.py`](agenarc/vfs/filesystem.py) - `agrc://` protocol mapping:
| VFS Path | Actual Path |
|----------|-------------|
| `agrc://prompts/` | `<bundle>/prompts/` |
| `agrc://scripts/` | `<bundle>/scripts/` |
| `agrc://assets/` | `<bundle>/assets/` |

### Node Types
[`schema.py:13-24`](agenarc/protocol/schema.py#L13-L24):
- `Trigger` - Entry point
- `LLM_Task` - LLM inference
- `Router` - Conditional branching
- `Loop_Control` - Feedback loop iteration (`done=False` continues, `done=True` exits)
- `Memory_I/O` - Persistent storage
- `Script_Node` - Custom Python scripts with AST safety
- `SUBGRAPH`, `Plugin` - Extended operators
- `Log`, `Context_Set`, `Context_Get` - Utility nodes

### Loop_Control Feedback Pattern
```
Loop_Control (done=False) → Body nodes → Loop_Control (accumulator_input)
                                              ↓
                              until done=True → exit loop
```

### .agrc Bundle Structure
```
my_agent.agrc/
├── manifest.json      # Permissions, autonomy level, immutable anchors
├── flow.json         # Graph definition
├── prompts/          # Prompt templates (agrc:// access)
├── scripts/          # Executable scripts (agrc:// access)
├── plugins/          # Embedded plugins (auto-discovered, Python only)
│   └── my_plugin/
│       ├── agenarc.json
│       └── plugin.py
└── assets/           # Static resources
```

## Key Patterns

### Adding a New Operator
1. Create class implementing `IOperator`
2. Register in [`BUILTIN_OPERATORS`](agenarc/operators/builtin.py) dict
3. Use `@property` for `name` (e.g., `"builtin.trigger"`)

### Error Handling
Nodes have optional [`ErrorHandling`](agenarc/protocol/schema.py#L143) config:
- `strategy`: retry | fallback | skip | abort
- `fallbackNode`: Alternative node to execute on failure
- Global error handler via `graph.errorNode`

### Checkpoint Usage
Set `node.checkpoint: true` in flow.json for automatic state snapshots before node execution.

### Plugin System (Stage 4 Complete)
Plugin system with three loader types:
- **PythonPluginLoader** - Dynamic import of Python plugins from `agenarc.json` manifests
- **CppPluginLoader** - ctypes loading of compiled `.so`/`.dll`/`.dylib` libraries
- **ExternalPluginLoader** - IPC via stdio JSON-RPC or HTTP REST

**Embedded plugins**: Python plugins can be placed in `<bundle>/plugins/` for distribution with the agent bundle.

Hot reload via [`hot_loader.py`](agenarc/plugins/hot_loader.py):
- File watching with watchdog (fallback to polling)
- Atomic plugin replacement (zero-downtime)
- Debounced reload (500ms) to avoid thrashing

Plugin manifest format:
```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "entry": "plugin.py",
  "operators": ["MyOperator"]
}
```

## Configuration

Environment variables (override `config.yaml`):
```bash
AGENARC_OPENAI_API_KEY      # OpenAI API key
AGENARC_OPENAI_BASE_URL     # OpenAI base URL
AGENARC_OPENAI_MODEL        # Default model
AGENARC_ANTHROPIC_API_KEY   # Anthropic API key
AGENARC_CHECKPOINT_DIR      # Checkpoint directory (default: ~/.agenarc/checkpoints/)
```

## File Locations
- Examples: `examples/*.agrc`
- Tests: `tests/unit/`, `tests/integration/`
- Config: `~/.agenarc/config.yaml` (also `config.yaml` in project root for backward compatibility)
- pytest.ini: `asyncio_mode = auto` for async test support
