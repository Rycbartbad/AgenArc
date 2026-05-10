# Changelog

All notable changes to AgenArc will be documented in this file.

## [0.7.1] - 2026-05-10

### Added
- Bundle file tree editor (left panel) with real-time editing and auto-save
- Floating editor modal with syntax highlighting (JSON keys, strings, comments, keywords)
- Syntax highlighter: single-pass character-by-character tokenizer
- SubGraph node frontend features — purple visual indicator, Inspector Open button
- Breadcrumb navigation: VFS card display, parent graph navigation
- `POST /api/graph/load` endpoint for sub-graph loading
- `GET /api/bundle/tree`, `GET /api/bundle/file`, `POST /api/bundle/file` API endpoints
- Edge obstacle avoidance for backward loop edges (later reverted due to arrow artifacts)

### Fixed
- SubGraph port dynamic resolution from operator classes (not empty node.outputs)
- Terminal node detection: only nodes with NO outgoing edges (not just no data edges)
- Real-time port updates on config change (updCfg → syncWithBackend)
- Save sub-graph edits to correct flow.json via `saveSubGraph()` — prevents parent corruption
- Remove orphaned textarea causing extra invisible panel
- Node metadata preserved in `_save_graph` — fixes 0ms execution after add/delete nodes
- Node statuses reset after `_save_graph` — prevents stale execution state
- Config field Enter key now triggers save
- All nodes unified left-border accent style, each type its own color
- CI: ruff import ordering, mypy type fixes

## [0.7.0] - 2026-05-10

### Added
- **SubGraph operator** — embed one `.agrc` bundle as a node in another graph
- Isolated execution context for sub-graph (separate StateManager)
- Port auto-resolution from child bundle's trigger outputs (input) and terminal node outputs (output)
- Child bundle port exposure via operator classes (`BUILTIN_OPERATORS`)
- Recursive sub-graph reference detection (`_resolving_stack`)
- `_resolve_subgraph_ports` in protocol loader for automatic port derivation
- `_get_node_output_ports` / `_get_node_input_ports` — resolve ports from operators if node.outputs is empty
- `agenarc pack` auto-embeds SubGraph bundles into `sub/` directory
- Bundle resolution fallback: `sub/{path}` if direct path not found

### Changed
- `NodeType.SUBGRAPH` value normalized to `"SubGraph"` (uppercase G)
- `_parse_node` now handles SubGraph port special case
- `_node_to_dict` reads SubGraph ports from Node object (not operator defaults)
- Path resolution order: direct → `sub/` → CWD

## [0.6.0] - 2026-05-09 / 0.6.1

### Added
- **Execution tracing**: TraceCollector engine with per-node timing, status, I/O snapshots, and token tracking
- **Trace API**: GET /api/trace/latest, GET /api/trace/{id}, GET /api/trace/list, POST /api/trace/export
- **Timeline panel**: Waterfall chart in visualization IDE — color-coded bars, auto-refresh, click-to-select, JSON export
- **agenarc init**: Interactive configuration wizard with 12 provider presets, real-time model fetching, connection testing, and config.yaml generation
- **Provider presets**: DeepSeek, OpenAI, Anthropic, Groq, OpenRouter, Ollama, 硅基流动, ZhipuAI, Moonshot, DashScope, 豆包, Custom
- **742 tests** (up from 638) — 48 trace + 56 init tests
- GitHub Release with standalone Windows exe (PyInstaller)
- `webbrowser.open()` auto-launch on `agenarc visualize`
- ASCII art startup banner
- `AGENTS.md` pre-push checklist (pytest + ruff + mypy)

## [0.5.0] - 2026-05-09

### Added
- **LLM streaming**: `stream=True` config option for real-time response streaming
- **Multi-provider fallback**: `providers` config tries multiple providers in order
- **Structured error output**: `error` port on LLM_Task with retryable/non-retryable classification
- **Visualization platform**: Web-based IDE with node graph editor, execution preview, context panel
- **Auto-save + undo/redo**: Lossless editing in visualization IDE
- **Integration tests**: 10 Router/Join tests covering conditions, strategies, and combined flows
- **CI workflow**: GitHub Actions with Python 3.11-3.13 matrix, pytest, ruff, mypy
- **EditorConfig + pre-commit hooks**: Consistent formatting across contributors
- **CONTRIBUTING.md**: Development setup, PR process, and commit style guide

### Changed
- **CLI refactor**: `__main__.py` split from 1348 lines into `commands/` subpackage (run, shell, serve, validate, info, pack, visualize)
- **Version bump**: 0.1.0 → 0.5.0
- **Classifier**: Alpha → Beta
- **Plugin module isolation**: Flat hash-based naming (`plug_{name}_{hash}`) for uniqueness

### Fixed
- **Context panel**: Now reads live engine state directly instead of stale tracker snapshots
- **Execution status**: Heartbeat no longer overwrites terminal "running" status
- **Router conditions**: Converted from dicts to `Condition` objects during parsing (fixes `'dict' object has no attribute 'and_conditions'`)
- **Condition operators**: Case-insensitive lookup (tests used uppercase, map had lowercase)
- **CheckpointManager**: Connected to engine state for proper persistence
- **Config**: Thread-safe singleton with double-lock, generic env var support
- **Operator timeout**: Added timeout support to prevent hung executions
- **VFS**: Path traversal safety improvements and encoding fixes
- **Plugin manager**: Initialization cleanup and hot loader edge cases

### Removed
- **Anthropic_Task_Operator**: Merged into LLM_Task_Operator with unified streaming/fallback

## [0.4.0] - 2026-04

### Added
- Plugin system with Python/C++/External loaders
- Hot_Plugin_Loader with file watching + atomic reload
- EventPlugin architecture (QQ bot, hotkey plugins)

## [0.3.0] - 2026-03

### Added
- .agrc bundle format (self-contained agent packages)
- VFS (`agrc://`) with rwx permission model
- Asset_Reader, Asset_Writer, Runtime_Reload operators
- Schema + AST sanitizer dual validation chain

## [0.2.0] - 2026-02

### Added
- Router operator (conditional branching)
- Join operator (parallel branch synchronization)
- Script_Node with AST safety levels
- CheckpointManager for interruption recovery
- AST evaluator for safe expression evaluation

## [0.1.0] - 2026-01

### Added
- JSON Schema protocol definition
- ExecutionEngine with linear flow
- Built-in operators: Trigger, Memory_I/O, Script_Node, Log, Context_Set, Context_Get
- CLI: `agenarc run`, `agenarc validate`, `agenarc info`
