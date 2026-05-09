# AGENTS.md — AgenArc

> Compact instruction file for AI agents working in this repository.
> Complements `CLAUDE.md`. Only includes things an agent would likely miss without help.

## ⛔ Before Push — MANDATORY CHECKLIST

**NEVER push without passing ALL three:**

```bash
# 1. Tests — must be 100% green
pytest tests/ -q

# 2. Lint — zero errors
ruff check agenarc/

# 3. Type check — zero errors
mypy agenarc/ --ignore-missing-imports
```

| Check | Command | Must Be |
|-------|---------|---------|
| Tests | `pytest tests/ -q` | All passed |
| Lint | `ruff check agenarc/` | All checks passed |
| Format | `ruff format --check agenarc/` | Already formatted |
| Types | `mypy agenarc/ --ignore-missing-imports` | 0 errors |

If any fails → fix it FIRST. Do NOT push broken code.

## First Reads

- `README.md` — project overview, features, quick start, CLI reference
- `CLAUDE.md` — detailed architecture, data flow, all operator types, template system, plugin system
- `ARCHITECTURE.md` — 570-line Chinese architecture spec with port definitions and AST safety details
- `docs/agents.md` — 1966-line user-facing guide for creating `.agrc` agents (not AI-agent instructions)
- `docs/plugins/README.md` — plugin development guide

## Setup & Package

- **No `setup.py` / `setup.cfg`** — this is a from-source project with `pyproject.toml` based build. Run via `python -m agenarc.cli`.
- **Config loading order**: `~/.agenarc/config.yaml` (preferred) → project root `config.yaml` (legacy fallback)
- **Two config formats**: legacy flat keys (`openai.api_key`) and `providers.{name}` nested format (`providers.deepseek.api_key`). `Config.get_provider_config()` checks `providers.{name}` first, then falls back to flat keys.
- **Env vars override config**: `AGENARC_OPENAI_API_KEY`, `AGENARC_OPENAI_BASE_URL`, `AGENARC_OPENAI_MODEL`, `AGENARC_ANTHROPIC_API_KEY`, `AGENARC_ANTHROPIC_MODEL`, `AGENARC_CHECKPOINT_DIR`
- **CLI version**: `0.6.0` (in `agenarc/__init__.py`)
- **`.gitignore` includes**: `config.yaml`, `.env`, `CLAUDE.md`, `ARCHITECTURE.md`
- **CI workflows**: `.github/workflows/ci.yml` (pytest + ruff + mypy on 3.11/3.12/3.13), `.github/workflows/publish.yml` (PyPI + GitHub Release with exe)
- **Pre-commit hooks**: `.pre-commit-config.yaml` (ruff + ruff-format)

## Developer Commands

All CLI commands require `PYTHONIOENCODING=utf-8` on Windows to handle Unicode:

```bash
# Run agent (.agrc bundle or .json)
PYTHONIOENCODING=utf-8 python -m agenarc.cli run <path> --input '{"payload":"Hello"}'

# Interactive shell (REPL)
PYTHONIOENCODING=utf-8 python -m agenarc.cli shell <path>

# Background service with event plugins (auto-detects plugins from source nodes)
PYTHONIOENCODING=utf-8 python -m agenarc.cli serve <path>

# Validate protocol
python -m agenarc.cli validate <path>

# Show agent info
python -m agenarc.cli info <path>

# Pack directory into .agrc ZIP bundle
python -m agenarc.cli pack <source_dir> [output.agrc]

# Interactive configuration wizard
python -m agenarc.cli init

# Start visualization server
python -m agenarc.cli visualize <path> --port 8765

# Run a single example (no LLM needed):
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/my_first_agent.agrc --input '{}'
```

### Run modes: `--mode sync | async | parallel` (default: async)

### Tests (742 passed, ~62% coverage)

```bash
pytest tests/                                                      # All tests
pytest tests/ --cov=agenarc --cov-report=term-missing              # With coverage
pytest tests/unit/test_builtin_operators.py -v                     # Single file
```

- `pytest.ini`: `asyncio_mode = auto` — all async test functions work automatically
- `DeprecationWarning` and `PendingDeprecationWarning` are suppressed in pytest
- Tests: 25 unit test files in `tests/unit/`, 1 integration test in `tests/integration/`

## Architecture Gotchas

### Core Data Flow
Node outputs stored in context as `nodes.{node_id}.{port_name}`. Downstream nodes read via edge's `sourcePort`.

### BUILTIN_OPERATORS Registry (agenarc/operators/builtin.py:795)
```python
BUILTIN_OPERATORS: Dict[str, type] = {
    "Trigger": TriggerOperator,       # in builtin.py
    "Memory_I/O": Memory_IO_Operator, # in builtin.py
    "Script_Node": ...,               # in builtin.py
    "Log": ...,                       # in builtin.py
    "Prompt_Builder": ...,            # in builtin.py — NOT a separate file
    "Context_Set": ...,
    "Context_Get": ...,
    "Join": None,                     # Loaded from join.py on import
    "Router": None,                   # Loaded from router.py on import
    "LLM_Task": None,                 # Loaded from llm.py on import
}
```
Key: `None` entries get populated by auto-registration functions called at module import time. `Asset_Reader`, `Asset_Writer`, `Runtime_Reload` are registered similarly from `evolution.py`.

### NodeType is a string Enum
Both `NodeType.TRIGGER` and the string `"Trigger"` work. But in JSON flow.json, always use the string value.

### Operators with Dynamic Ports
- **Router**: Does NOT declare fixed output ports. Output ports are determined by edges via `sourcePort`. `condition.output` labels match `edge.sourcePort`.
- **Join**: Does NOT declare fixed input ports. Reads dynamically from `_incoming_edges` (context `nodes.{source}.{sourcePort}`).

### Entry Point Deprecated
Source nodes are auto-detected (nodes with no incoming edges). Do NOT use `entryPoint` — it was removed.

### Edge Simplified Syntax
When edge target is `trigger`, only `source` and `target` fields are needed (control-flow only, no data passed):
```json
{"source": "pb_assistant", "target": "trigger_1"}
```

### Two Prompt_Builders Sharing History = Multi-Turn
Two `Prompt_Builder` nodes with same `config.history` key enable multi-turn conversation:
- `pb_user` (receives `user` input) + `pb_assistant` (receives `assistant` input) share `history: "chat_history"`
- Edge `pb_assistant → trigger` signals session persistence
- `user` and `assistant` input ports are **mutually exclusive** — alternation enforced

### Script_Node Trust Levels
- `locked`: Expressions only (via AST evaluator with gas limits)
- `trusted`: Safe statements with restricted builtins
- `developer` (**default**): **Unrestricted** — has `__builtins__`, imports `os`, `websockets`, `socket`, `struct`, `base64`, `json`, `urllib`. Full Python access.

### Memory_I/O Features
- Modes: `read` | `write` | `delete`
- Supports `transactional` writes (pending list, commit on success) and `checkpoint` persistence to disk

## Shell REPL Commands

| Command | Action |
|---------|--------|
| `:reset` | Reset session (clear context, new conversation) |
| `:quit` / `:exit` | Exit shell |
| `:info` | Show source nodes, node/edge count |
| `:logs` | Toggle execution log display |
| `:results` | Toggle result display |
| `:load <path>` | Load new agent without restarting |
| `:mode <mode>` | Set execution mode |

Shell input: plain text → `{"payload": "<text>"}`, JSON object → used as-is.

## .agrc Bundle Format

Bundles can be either:
- **Directory** (development): `my_agent.agrc/` with `manifest.json` + `flow.json`
- **ZIP archive** (distribution): Packed via `agenarc pack` command (like JAR files)

The CLI auto-detects which format is being used via `_resolve_bundle_path()` in `cli/__main__.py`.

## Plugin System Details

Three loader types (all in `agenarc/plugins/loaders/`):
- `python.py` — Dynamic import from `agenarc.json` manifests
- `cpp.py` — ctypes loading of `.so`/`.dll`/`.dylib`
- `external.py` — IPC via stdio JSON-RPC or HTTP REST

**Plugin locations** (checked in order):
1. Global: `~/.agenarc/plugins/`
2. Embedded in bundle: `<bundle>/plugins/` (Python only, auto-discovered)
3. Bundle assets: `<bundle>/assets/plugins/` (C++/External, auto-installed to global)

**Event plugins** are separate from regular operators — they listen for external events via `agenarc serve` command. Auto-detected from source Plugin nodes in the graph.

## MCP Directory
The `agenarc/mcp/` directory referenced in `CLAUDE.md` does NOT exist in the codebase. MCP support was planned but not implemented.

## Router & Join
Router and Join operators now function correctly. Router conditions evaluate against context values, and Join collects inputs from all incoming edges. No workaround needed.

## Visualization Module
Located in `agenarc/visualization/` (server.py, events.py, state.py). Started via `agenarc visualize <path>`. Serves a web-based IDE at `http://localhost:8765` for node editing and execution preview.

## Template Resolution
- `{{key}}` resolved at **execution time** (not load time)
- Max recursive depth: 10
- Dot access: `{{user.name}}`
- VFS integration: `agrc://prompts/system.pt` reads file content first, then resolves templates
- Functions: `resolve_template()`, `resolve_template_dict()`, `resolve_template_any()`, `resolve_vfs_and_template()` in `engine/evaluator.py`

## VFS Permission Model (rwx)
In `manifest.json` permissions:
```json
{"permissions": {"prompts": "r--", "scripts": "rw-", "assets": "r--"}}
```
- `r`: read, `w`: write, `x`: execute
- Subdirectories inherit parent permissions
- Unconfigured paths default to `---` (inaccessible, list_dir returns empty)

## Important File Locations

| What | Where |
|------|-------|
| CLI entry | `agenarc/cli/__main__.py` (~280 lines, dispatches to `commands/` subpackage) |
| CLI commands | `agenarc/cli/commands/` (run, shell, serve, validate, info, pack, visualize, init) |
| All operators builtin | `agenarc/operators/builtin.py` (Trigger, Memory_I/O, Script_Node, Log, Prompt_Builder, Context_Set, Context_Get) |
| Evolution operators | `agenarc/operators/evolution.py` (Asset_Reader, Asset_Writer, Runtime_Reload) |
| Execution tracing | `agenarc/engine/trace.py` (NodeTrace, TraceCollector) |
| Graph types | `agenarc/graph/traversal.py`, `agenarc/protocol/schema.py` |
| State management | `agenarc/engine/state.py` |
| AST evaluator | `agenarc/engine/evaluator.py` |
| Executor | `agenarc/engine/executor.py` |
| Examples | `examples/*.agrc/` (directories: euchea, my_first_agent, qq_bot) |
| User guide | `docs/agents.md` (1966 lines, in Chinese) |
| PyInstaller spec | `AgenArc.spec` (standalone exe build) |
