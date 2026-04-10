"""
AgenArc CLI

Command-line interface for AgenArc execution engine.

Usage:
    agenarc run <agent.agrc|flow.json>
    agenarc shell <agent.agrc|flow.json>
    agenarc validate <agent.agrc|flow.json>
    agenarc info <agent.agrc|flow.json>
    agenarc pack <directory> [output.agrc]
"""

import argparse
import asyncio
import code
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from agenarc import __version__
from agenarc.engine.executor import ExecutionEngine, ExecutionMode
from agenarc.engine.state import StateManager
from agenarc.operators.builtin import BUILTIN_OPERATORS
from agenarc.plugins.manager import PluginManager
from agenarc.protocol.loader import ProtocolLoader, LoaderError


def _install_bundle_plugins(bundle_path: Path, verbose: bool = False) -> None:
    """
    Install plugins from bundle's assets/plugins/ to global plugins directory.

    Args:
        bundle_path: Path to the agent bundle
        verbose: Print verbose output
    """
    import shutil
    import json

    assets_plugins_dir = bundle_path / "assets" / "plugins"
    if not assets_plugins_dir.exists():
        return

    global_plugins_dir = Path("~/.agenarc/plugins").expanduser()
    global_plugins_dir.mkdir(parents=True, exist_ok=True)

    for plugin_dir in assets_plugins_dir.iterdir():
        if not plugin_dir.is_dir():
            continue

        agenarc_json = plugin_dir / "agenarc.json"
        if not agenarc_json.exists():
            continue

        target_dir = global_plugins_dir / plugin_dir.name

        # Check if already installed (skip if same or older)
        if target_dir.exists():
            target_meta = target_dir / "agenarc.json"
            if target_meta.exists():
                try:
                    with open(target_meta, "r", encoding="utf-8") as f:
                        target_version = json.load(f).get("version", "0")
                    with open(agenarc_json, "r", encoding="utf-8") as f:
                        source_version = json.load(f).get("version", "0")
                    if target_version >= source_version:
                        if verbose:
                            print(f"Plugin '{plugin_dir.name}' already installed (v{target_version})")
                        continue
                except Exception:
                    pass

        # Copy plugin to global directory
        if verbose:
            print(f"Installing plugin '{plugin_dir.name}' to global plugins directory...")

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(plugin_dir, target_dir)


# Cache for extracted .agrc bundles: bundle_path -> extraction_dir
_agrc_cache: Dict[Path, Path] = {}


def _extract_agrc(agrc_path: Path, verbose: bool = False) -> Path:
    """
    Extract .agrc bundle to a temp directory.

    .agrc is a ZIP-based archive format like JAR.
    Extracted contents are cached for the session.

    Args:
        agrc_path: Path to .agrc file
        verbose: Print verbose output

    Returns:
        Path to extracted bundle directory (path containing flow.json)
    """
    import zipfile
    import tempfile

    if agrc_path in _agrc_cache:
        return _agrc_cache[agrc_path]

    if verbose:
        print(f"Extracting {agrc_path}...")

    extract_dir = Path(tempfile.mkdtemp(prefix="agenarc_"))

    with zipfile.ZipFile(agrc_path, "r") as zf:
        zf.extractall(extract_dir)

    # Find the directory containing flow.json
    # Handle case where zip contains a subdirectory (e.g., my_agent/flow.json)
    flow_file = extract_dir / "flow.json"
    if flow_file.exists():
        _agrc_cache[agrc_path] = extract_dir
        return extract_dir

    # Look for flow.json in subdirectories
    for item in extract_dir.iterdir():
        if item.is_dir():
            if (item / "flow.json").exists():
                _agrc_cache[agrc_path] = item
                return item

    # Fallback: return root
    _agrc_cache[agrc_path] = extract_dir
    return extract_dir


def _resolve_bundle_path(file_path: Path) -> Path:
    """
    Resolve a bundle path to the actual protocol file.

    Supports:
    - .agrc ZIP bundles (like JAR)
    - .agrc directory bundles (for development)
    - .json files (direct protocol)

    Args:
        file_path: Input path from user

    Returns:
        Path to the protocol JSON file or extracted bundle directory
    """
    path = Path(file_path)

    # .agrc ZIP file
    if path.suffix == ".agrc" and path.is_file():
        extract_dir = _extract_agrc(path)
        return extract_dir

    # .agrc directory (development mode)
    if path.suffix == ".agrc" and path.is_dir():
        flow_file = path / "flow.json"
        if flow_file.exists():
            return path
        manifest_file = path / "manifest.json"
        if manifest_file.exists():
            return path

    # Regular JSON file
    if path.suffix == ".json":
        return path

    # Fallback: treat as directory bundle (legacy .agrc behavior)
    if path.is_dir():
        flow_file = path / "flow.json"
        if flow_file.exists():
            return path
        manifest_file = path / "manifest.json"
        if manifest_file.exists():
            return path

    return path


def pack_bundle(source_dir: Path, output_path: Path, verbose: bool = False) -> None:
    """
    Pack a directory into a .agrc ZIP bundle.

    Args:
        source_dir: Source directory to pack
        output_path: Output .agrc file path
        verbose: Print verbose output
    """
    import zipfile

    if verbose:
        print(f"Packing {source_dir} -> {output_path}...")

    output_path = Path(output_path)
    if not output_path.suffix == ".agrc":
        output_path = Path(str(output_path) + ".agrc")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(source_dir)
                zf.write(file_path, arcname)
                if verbose:
                    print(f"  Adding: {arcname}")

    if verbose:
        print(f"Bundle created: {output_path}")


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="agenarc",
        description="Directed-graph Agent Orchestration Engine"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"agenarc {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run command
    run_parser = subparsers.add_parser(
        "run",
        help="Execute an agent (.agrc or .json)"
    )
    run_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )
    run_parser.add_argument(
        "--input",
        "-i",
        type=str,
        help="Initial input as JSON string"
    )
    run_parser.add_argument(
        "--mode",
        "-m",
        choices=["sync", "async", "parallel"],
        default="async",
        help="Execution mode"
    )
    run_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    # serve command (service mode with event plugins)
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start agent as a background service with event plugins"
    )
    serve_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )
    serve_parser.add_argument(
        "--mode",
        "-m",
        choices=["sync", "async", "parallel"],
        default="async",
        help="Execution mode"
    )
    serve_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    serve_parser.add_argument(
        "--plugins",
        "-p",
        type=str,
        default="",
        help="Comma-separated list of event plugins to load (default: all)"
    )
    serve_parser.add_argument(
        "--plugin-config",
        type=str,
        default="",
        help="JSON string with plugin configuration (e.g., '{\"qq\":{\"ws_url\":\"ws://127.0.0.1:3002\"}}')"
    )

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate an agent bundle or protocol"
    )
    validate_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )

    # info command
    info_parser = subparsers.add_parser(
        "info",
        help="Show agent/protocol information"
    )
    info_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )

    # pack command
    pack_parser = subparsers.add_parser(
        "pack",
        help="Pack a directory into a .agrc bundle"
    )
    pack_parser.add_argument(
        "source",
        type=Path,
        help="Source directory to pack"
    )
    pack_parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Output .agrc file path (default: <source>.agrc)"
    )
    pack_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    # shell command
    shell_parser = subparsers.add_parser(
        "shell",
        help="Interactive shell for agent execution"
    )
    shell_parser.add_argument(
        "file",
        type=Path,
        help="Path to agent bundle (.agrc) or protocol (.json)"
    )
    shell_parser.add_argument(
        "--mode",
        "-m",
        choices=["sync", "async", "parallel"],
        default="async",
        help="Execution mode"
    )
    shell_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    shell_parser.add_argument(
        "--log",
        "-l",
        action="store_true",
        help="Show execution logs"
    )

    return parser


def print_error(message: str) -> None:
    """Print error message to stderr."""
    print(f"ERROR: {message}", file=sys.stderr)


def print_success(message: str) -> None:
    """Print success message."""
    print(f"SUCCESS: {message}")


class InteractiveREPL:
    """Interactive REPL for AgenArc agent execution with session persistence."""

    def __init__(
        self,
        engine: ExecutionEngine,
        protocol_path: Path,
        verbose: bool = False,
        show_logs: bool = False
    ):
        self.engine = engine
        self.protocol_path = protocol_path
        self.verbose = verbose
        self.show_logs = show_logs
        self.show_results = False
        self._history: List[str] = []
        self._session_state: Optional[StateManager] = None  # Session-persistent StateManager
        self._session_initialized = False  # Flag: has Trigger run this session

    def _print_banner(self) -> None:
        """Print REPL banner."""
        print("=" * 50)
        print("AgenArc Interactive Shell")
        print("=" * 50)
        print(f"Agent: {self.protocol_path}")
        print("Context persists during session, resets on new session")
        print("Type input and press Enter to execute")
        print("  - Plain text: treated as payload")
        print("  - JSON object: used as full payload")
        print("Commands: :quit/:exit to exit, :reset to start new session")
        print("          :info to show agent info, :logs to toggle logs, :results to toggle output")
        print("=" * 50)
        print()

    def _print_result(self, result: Any, is_error: bool = False) -> None:
        """Print execution result."""
        if is_error:
            print(f"ERROR: {result}")
        else:
            if isinstance(result, dict):
                print(json.dumps(result, indent=2, default=str))
            else:
                print(result)

    def _handle_command(self, line: str) -> Optional[bool]:
        """
        Handle special REPL commands.

        Returns:
            True if should continue, False if should exit, None if not a command
        """
        cmd = line.strip().lower()

        if cmd in (":quit", ":exit", "exit", "quit", "q"):
            print("Goodbye!")
            return False

        if cmd == ":reset":
            # Reset session state (new session starts)
            self._session_state = None
            self._session_initialized = False
            self.engine._state = StateManager()
            self.engine._state.initialize(
                self.engine._execution_id or "reset",
                self.engine._graph.entryPoint if self.engine._graph else "agent"
            )
            print("Session reset (new conversation started).")
            return True

        if cmd == ":info":
            if self.engine._graph:
                print(f"Entry Point: {self.engine._graph.entryPoint}")
                print(f"Nodes: {len(self.engine._graph.nodes)}")
                print(f"Edges: {len(self.engine._graph.edges)}")
                print(f"Status: {self.engine._graph.entryPoint or 'unknown'}")
            else:
                print("No agent loaded.")
            return True

        if cmd == ":logs":
            self.show_logs = not self.show_logs
            print(f"Logs {'enabled' if self.show_logs else 'disabled'}.")
            return True

        if cmd == ":results":
            self.show_results = not self.show_results
            print(f"Results {'enabled' if self.show_results else 'disabled'}.")
            return True

        if cmd.startswith(":load "):
            # Load new agent
            new_path = Path(cmd[6:].strip())
            try:
                self.engine.load_protocol(new_path)
                self.protocol_path = new_path
                print(f"Loaded: {new_path}")
            except Exception as e:
                print(f"ERROR: Failed to load: {e}")
            return True

        if cmd.startswith(":mode "):
            mode = cmd[6:].strip()
            self.engine.max_parallel = 4  # default
            print(f"Mode set to: {mode}")
            return True

        # Not a special command
        return None

    def _execute_payload(self, payload: Dict[str, Any]) -> tuple:
        """Execute payload and return (result, error, logs)."""
        exec_mode = ExecutionMode.ASYNC

        try:
            # Check if trigger has incoming edges (determines multi-turn session)
            trigger_node = self.engine._graph.get_node(self.engine._graph.entryPoint)
            incoming_edges = self.engine._graph.get_incoming_edges(trigger_node.id)
            has_incoming = len(incoming_edges) > 0

            if not has_incoming:
                # No incoming edges: fresh state for each execution
                self._session_state = StateManager(
                    auto_checkpoint=self.engine.enable_checkpoint
                )
                self._session_state.initialize(
                    self.engine._execution_id or "session",
                    self.engine._graph.entryPoint if self.engine._graph else "agent"
                )
                self._session_initialized = False
            else:
                # Has incoming edges: maintain session state (multi-turn conversation)
                if self._session_state is None:
                    self._session_state = StateManager(
                        auto_checkpoint=self.engine.enable_checkpoint
                    )
                    self._session_state.initialize(
                        self.engine._execution_id or "session",
                        self.engine._graph.entryPoint if self.engine._graph else "agent"
                    )
                    self._session_initialized = False
                else:
                    self._session_initialized = True

            # Attach session StateManager to engine
            self.engine._state = self._session_state

            # Mark if this is the first execution (Trigger will run)
            self.engine._state.set_global("_session_first_run", not self._session_initialized)

            result = asyncio.run(self.engine.execute(payload, exec_mode))
            return result.final_outputs, None, result.node_results
        except Exception as e:
            return None, str(e), None

    def run(self) -> None:
        """Run the interactive REPL."""
        self._print_banner()

        while True:
            try:
                line = input("agenarc> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not line:
                continue

            # Add to history
            self._history.append(line)

            # Check for special commands
            cmd_result = self._handle_command(line)
            if cmd_result is False:
                break  # Exit
            if cmd_result is True:
                continue  # Command handled, continue

            # Parse input: plain text or JSON
            stripped = line.strip()
            if stripped.startswith("{"):
                # Try to parse as JSON
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as e:
                    print(f"ERROR: Invalid JSON: {e}")
                    continue
            else:
                # Plain text - wrap as payload
                payload = {"payload": stripped}

            # Execute
            if self.verbose:
                print(f"Executing with payload: {json.dumps(payload)[:100]}...")

            outputs, error, node_results = self._execute_payload(payload)

            if self.show_logs and node_results:
                print("\n--- Execution Logs ---")
                for node_id, result in node_results.items():
                    status_name = result.status.name if hasattr(result.status, 'name') else str(result.status)
                    print(f"[{node_id}] {status_name}")
                    if result.outputs:
                        for key, value in result.outputs.items():
                            print(f"  {key}: {value}")
                    if result.error:
                        print(f"  ERROR: {result.error}")
                print("---")

            if error:
                print(f"ERROR: {error}")
            elif self.show_results:
                print("\n--- Results ---")
                self._print_result(outputs)
                print("---")

        print(f"Executed {len(self._history)} commands.")


def command_shell(
    file: Path,
    mode: str = "async",
    verbose: bool = False,
    show_logs: bool = False
) -> int:
    """
    Start an interactive shell for agent execution.

    Args:
        file: Path to agent bundle (.agrc) or protocol (.json)
        mode: Execution mode
        verbose: Verbose output flag
        show_logs: Show execution logs

    Returns:
        Exit code
    """
    # Resolve bundle path
    protocol_path = _resolve_bundle_path(file)

    # Determine bundle path
    bundle_path = None
    if protocol_path.is_dir():
        bundle_path = protocol_path
        _install_bundle_plugins(bundle_path, verbose)

    # Create engine
    plugin_manager = PluginManager(bundle_paths=[bundle_path] if bundle_path else [])
    engine = ExecutionEngine(plugin_manager=plugin_manager)

    # Register built-in operators
    for node_type, operator_class in BUILTIN_OPERATORS.items():
        engine.register_builtin_operator(node_type, operator_class)

    # Load protocol
    try:
        engine.load_protocol(protocol_path)
    except LoaderError as e:
        print_error(f"Failed to load protocol: {e}")
        return 1
    except ValueError as e:
        print_error(f"Invalid protocol: {e}")
        return 1

    # Start interactive shell
    repl = InteractiveREPL(
        engine=engine,
        protocol_path=protocol_path,
        verbose=verbose,
        show_logs=show_logs
    )

    repl.run()

    return 0


def command_run(
    file: Path,
    input_json: Optional[str] = None,
    mode: str = "async",
    verbose: bool = False
) -> int:
    """
    Execute an agent bundle or protocol file.

    Args:
        file: Path to agent bundle (.agrc) or protocol (.json)
        input_json: Initial input as JSON string
        mode: Execution mode
        verbose: Verbose output flag

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Resolve bundle path
    protocol_path = _resolve_bundle_path(file)

    # Determine bundle path (directory for .agrc bundles, None for standalone .json)
    bundle_path = None
    if protocol_path.is_dir():
        bundle_path = protocol_path
        # Install plugins from bundle assets to global plugins directory
        _install_bundle_plugins(bundle_path, verbose)

    # Parse initial inputs
    initial_inputs = {}
    if input_json:
        try:
            initial_inputs = json.loads(input_json)
        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON in --input: {e}")
            return 1

    # Create engine
    plugin_manager = PluginManager(bundle_paths=[bundle_path] if bundle_path else [])
    engine = ExecutionEngine(plugin_manager=plugin_manager)

    # Register built-in operators
    for node_type, operator_class in BUILTIN_OPERATORS.items():
        engine.register_builtin_operator(node_type, operator_class)

    # Load protocol
    if verbose:
        print(f"Loading agent from {protocol_path}...")

    try:
        engine.load_protocol(protocol_path)
    except LoaderError as e:
        print_error(f"Failed to load protocol: {e}")
        return 1
    except ValueError as e:
        print_error(f"Invalid protocol: {e}")
        return 1

    # Choose execution mode
    exec_mode = {
        "sync": ExecutionMode.SYNC,
        "async": ExecutionMode.ASYNC,
        "parallel": ExecutionMode.PARALLEL
    }.get(mode, ExecutionMode.ASYNC)

    # Execute
    if verbose:
        print(f"Executing graph (mode={mode})...")

    try:
        result = asyncio.run(engine.execute(initial_inputs, exec_mode))
    except Exception as e:
        print_error(f"Execution failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1

    # Print results
    if verbose:
        print(f"\nExecution completed in {result.duration_ms:.2f}ms")
        print(f"Status: {result.status}")

        if result.error:
            print(f"Error: {result.error}")

        print("\nNode Results:")
        for node_id, node_result in result.node_results.items():
            status = node_result.status.name
            outputs = node_result.outputs
            print(f"  {node_id}: {status}")
            if outputs:
                print(f"    Outputs: {json.dumps(outputs, default=str)}")

    else:
        # Simple output
        if result.status == "success":
            print_success(f"Execution completed in {result.duration_ms:.2f}ms")
            return 0
        else:
            print_error(f"Execution {result.status}")
            if result.error:
                print_error(str(result.error))
            return 1

    return 0


def command_validate(file: Path) -> int:
    """
    Validate an agent bundle or protocol file.

    Args:
        file: Path to agent bundle (.agrc) or protocol (.json)

    Returns:
        Exit code (0 for valid, 1 for invalid)
    """
    # Resolve bundle path
    protocol_path = _resolve_bundle_path(file)

    try:
        loader = ProtocolLoader(validate=True)
        graph = loader.load(protocol_path)

        print_success(f"Protocol is valid")
        print(f"  Version: {graph.version}")
        print(f"  Entry Point: {graph.entryPoint}")
        print(f"  Nodes: {len(graph.nodes)}")
        print(f"  Edges: {len(graph.edges)}")

        return 0

    except LoaderError as e:
        print_error(f"Validation failed: {e}")
        return 1


async def _start_event_plugins(
    engine: ExecutionEngine,
    plugin_manager: PluginManager,
    selected_plugins: Optional[List[str]] = None,
    plugin_configs: Optional[Dict[str, Dict[str, Any]]] = None
) -> None:
    """
    Start event plugins and register them with the plugin manager.

    Args:
        engine: Execution engine instance
        plugin_manager: Plugin manager instance
        selected_plugins: List of plugin names to start, or None for all
    """
    # Import event plugin base
    from agenarc.plugins.event_plugin import TriggerCallback

    # Create trigger callback
    trigger_callback = TriggerCallback(engine)
    trigger_callback.start()

    # Built-in event plugins
    built_in_plugins = {
        "qq": "agenarc.plugins.qq_plugin.plugin.QQPlugin",
    }

    # Load selected plugins
    plugins_to_load = []
    if selected_plugins:
        # Load specified plugins only
        for name in selected_plugins:
            if name in built_in_plugins:
                plugins_to_load.append((name, built_in_plugins[name]))
    else:
        # Load all built-in plugins
        plugins_to_load = list(built_in_plugins.items())

    # Load and start each plugin
    for plugin_name, plugin_class_path in plugins_to_load:
        try:
            # Import and instantiate plugin
            module_path, class_name = plugin_class_path.rsplit(".", 1)
            import importlib
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
            plugin_instance = plugin_class()

            # Build plugin configuration from multiple sources (later sources override earlier):
            # 1. From config.yaml: plugins.qq.*
            # 2. From --plugin-config CLI argument
            plugin_cfg = {}

            # Load from config file (config.yaml)
            try:
                from agenarc.config import get_config
                config = get_config()
                file_config = config.get(f"plugins.{plugin_name}", {})
                if file_config:
                    plugin_cfg.update(file_config)
                    print(f"[CLI] Loaded config for {plugin_name}: {plugin_cfg}")
            except Exception as e:
                print(f"[CLI] Config load error: {e}")

            # Override from CLI argument
            if plugin_configs and plugin_name in plugin_configs:
                plugin_cfg.update(plugin_configs[plugin_name])

            if hasattr(plugin_instance, 'configure'):
                plugin_instance.configure(plugin_cfg)

            # Register with plugin manager
            plugin_manager.register_event_plugin(plugin_name, plugin_instance)

            # Start the plugin
            await plugin_manager.start_event_plugin(plugin_name, trigger_callback)
            print(f"[CLI] Started event plugin: {plugin_name}")

        except Exception as e:
            print(f"[CLI] Failed to start plugin '{plugin_name}': {e}")

    # Store callback reference to prevent garbage collection
    engine._event_trigger_callback = trigger_callback


def command_serve(
    file: Path,
    mode: str = "async",
    verbose: bool = False,
    plugins: str = "",
    plugin_config: str = ""
) -> int:
    """
    Start agent as a background service with event plugins.

    Args:
        file: Path to agent bundle (.agrc) or protocol (.json)
        mode: Execution mode
        verbose: Verbose output flag
        plugins: Comma-separated list of plugins to load

    Returns:
        Exit code
    """
    import signal

    # Resolve bundle path
    protocol_path = _resolve_bundle_path(file)

    # Determine bundle path
    bundle_path = None
    if protocol_path.is_dir():
        bundle_path = protocol_path
        _install_bundle_plugins(bundle_path, verbose)

    # Parse selected plugins
    selected_plugins = None
    if plugins:
        selected_plugins = [p.strip() for p in plugins.split(",") if p.strip()]

    # Parse plugin configs
    plugin_configs: Dict[str, Dict[str, Any]] = {}
    if plugin_config:
        try:
            plugin_configs = json.loads(plugin_config)
        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON in --plugin-config: {e}")
            return 1

    # Create engine with bundle path for embedded plugin discovery
    import agenarc
    package_plugins_dir = str(Path(agenarc.__file__).parent / "plugins")
    plugin_manager = PluginManager(
        plugin_dirs=[package_plugins_dir],
        bundle_paths=[bundle_path] if bundle_path else []
    )
    engine = ExecutionEngine(plugin_manager=plugin_manager)

    # Register built-in operators
    for node_type, operator_class in BUILTIN_OPERATORS.items():
        engine.register_builtin_operator(node_type, operator_class)

    # Load protocol
    if verbose:
        print(f"Loading agent from {protocol_path}...")

    try:
        engine.load_protocol(protocol_path)
    except LoaderError as e:
        print_error(f"Failed to load protocol: {e}")
        return 1
    except ValueError as e:
        print_error(f"Invalid protocol: {e}")
        return 1

    # Choose execution mode
    exec_mode = {
        "sync": ExecutionMode.SYNC,
        "async": ExecutionMode.ASYNC,
        "parallel": ExecutionMode.PARALLEL
    }.get(mode, ExecutionMode.ASYNC)

    # Create event loop and start event plugins
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Set up signal handlers for graceful shutdown
    stop_event = asyncio.Event()

    def signal_handler(sig, frame):
        print("\n[CLI] Received stop signal, shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    async def run_service():
        """Run the service with event plugins."""
        # Initialize plugin manager to discover operators
        await plugin_manager.initialize()

        await _start_event_plugins(engine, plugin_manager, selected_plugins, plugin_configs)

        print(f"\n[CLI] AgenArc service started")
        print(f"[CLI] Entry point: {engine._graph.entryPoint}")
        print(f"[CLI] Mode: {mode}")
        if selected_plugins:
            print(f"[CLI] Plugins: {', '.join(selected_plugins)}")
        if plugin_configs:
            print(f"[CLI] Plugin config: {json.dumps(plugin_configs)}")
        print("[CLI] Press Ctrl+C to stop...\n")

        # Wait for stop signal
        try:
            # Also monitor plugin manager for stop events
            while not stop_event.is_set():
                # Check every 100ms if stop is requested
                await asyncio.sleep(0.1)
        finally:
            # Cleanup - stop all event plugins
            await plugin_manager.stop_all_event_plugins()
            await plugin_manager.shutdown()

    try:
        loop.run_until_complete(run_service())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

    print("[CLI] Service stopped.")
    return 0


def command_info(file: Path) -> int:
    """
    Show agent/protocol information.

    Args:
        file: Path to agent bundle (.agrc) or protocol (.json)

    Returns:
        Exit code
    """
    # Resolve bundle path
    protocol_path = _resolve_bundle_path(file)

    try:
        loader = ProtocolLoader(validate=False)
        graph = loader.load(protocol_path)

        # Try to load manifest for additional info
        manifest_path = protocol_path / "manifest.json" if protocol_path.is_dir() else protocol_path.parent / "manifest.json"
        manifest_name = ""
        manifest_description = ""
        manifest_author = ""
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    manifest_data = json.load(f)
                    manifest_name = manifest_data.get("name", "")
                    manifest_description = manifest_data.get("description", "")
                    manifest_author = manifest_data.get("author", "")
            except Exception:
                pass

        print(f"AgenArc Protocol Information")
        print(f"=" * 40)
        print(f"Version: {graph.version}")
        print(f"Entry Point: {graph.entryPoint}")
        if manifest_name:
            print(f"Name: {manifest_name}")
        if manifest_description:
            print(f"Description: {manifest_description}")
        if manifest_author:
            print(f"Author: {manifest_author}")

        print(f"\nNodes ({len(graph.nodes)}):")
        for node in graph.nodes:
            print(f"  [{node.type.value}] {node.id}")
            print(f"    Label: {node.label}")
            if node.inputs:
                inputs = ", ".join([p.name for p in node.inputs])
                print(f"    Inputs: {inputs}")
            if node.outputs:
                outputs = ", ".join([p.name for p in node.outputs])
                print(f"    Outputs: {outputs}")

        print(f"\nEdges ({len(graph.edges)}):")
        for edge in graph.edges:
            print(f"  {edge.source} -> {edge.target}")

        return 0

    except LoaderError as e:
        print_error(f"Failed to load protocol: {e}")
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point.

    Args:
        argv: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "run":
        return command_run(
            file=args.file,
            input_json=args.input,
            mode=args.mode,
            verbose=args.verbose
        )
    elif args.command == "validate":
        return command_validate(file=args.file)
    elif args.command == "info":
        return command_info(file=args.file)
    elif args.command == "pack":
        output = args.output or Path(str(args.source) + ".agrc")
        pack_bundle(args.source, output, args.verbose)
        return 0
    elif args.command == "shell":
        return command_shell(
            file=args.file,
            mode=args.mode,
            verbose=args.verbose,
            show_logs=args.log
        )
    elif args.command == "serve":
        return command_serve(
            file=args.file,
            mode=args.mode,
            verbose=args.verbose,
            plugins=args.plugins,
            plugin_config=args.plugin_config
        )
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
