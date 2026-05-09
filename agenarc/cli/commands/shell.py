"""
Command: shell — Interactive REPL for agent execution.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from agenarc.engine.executor import ExecutionEngine, ExecutionMode
from agenarc.engine.state import StateManager
from agenarc.operators.builtin import BUILTIN_OPERATORS
from agenarc.plugins.manager import PluginManager
from agenarc.protocol.loader import LoaderError

from . import _install_bundle_plugins, _resolve_bundle_path, print_error

logger = logging.getLogger(__name__)


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
        self._history: list[str] = []
        self._session_state: StateManager | None = None  # Session-persistent StateManager
        self._session_initialized = False  # Flag: has Trigger run this session
        self._exec_mode: ExecutionMode = ExecutionMode.ASYNC  # Default execution mode

    def _print_banner(self) -> None:
        """Print REPL banner."""
        print("=" * 50)
        print("AgenArc Interactive Shell")
        print("=" * 50)
        print(f"Agent: {self.protocol_path}")
        print("Context persists during session, resets on new session")
        print("Type input and press Enter to execute")
        print("  - Plain text: treated as payload string")
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

    def _handle_command(self, line: str) -> bool | None:
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
            source_nodes = self.engine._find_source_nodes()
            graph_id = source_nodes[0].id if source_nodes else "agent"
            self.engine._state.initialize(
                self.engine._execution_id or "reset",
                graph_id
            )
            print("Session reset (new conversation started).")
            return True

        if cmd == ":info":
            if self.engine._graph:
                source_nodes = self.engine._find_source_nodes()
                source_ids = [n.id for n in source_nodes]
                print(f"Source Nodes: {source_ids}")
                print(f"Nodes: {len(self.engine._graph.nodes)}")
                print(f"Edges: {len(self.engine._graph.edges)}")
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
            mode_str = cmd[6:].strip()
            mode_map = {
                "sync": ExecutionMode.SYNC,
                "async": ExecutionMode.ASYNC,
                "parallel": ExecutionMode.PARALLEL,
            }
            if mode_str in mode_map:
                self._exec_mode = mode_map[mode_str]
                print(f"Mode set to: {mode_str}")
            else:
                print(f"Unknown mode: {mode_str}. Use sync, async, or parallel.")
            return True

        # Not a special command
        return None

    def _execute_payload(self, payload: dict[str, Any]) -> tuple:
        """Execute payload and return (result, error, logs)."""
        exec_mode = self._exec_mode

        try:
            # In shell mode, Trigger acts as the entry point that normalizes input
            # Reuse session StateManager across calls so context persists (multi-turn)
            if self._session_state is None:
                self._session_state = StateManager(
                    auto_checkpoint=self.engine.enable_checkpoint
                )
                source_nodes = self.engine._find_source_nodes()
                graph_id = source_nodes[0].id if source_nodes else "shell"
                self._session_state.initialize(
                    self.engine._execution_id or "session",
                    graph_id
                )
                self._session_initialized = False
            else:
                self._session_initialized = True

            # Attach session StateManager to engine
            self.engine._state = self._session_state

            # Mark if this is the first execution (Trigger will run)
            self.engine._state.set_global("_session_first_run", not self._session_initialized)

            # Shell acts as a source node: store payload for Trigger to consume
            # Trigger reads from context.payload
            self.engine._state.set_global("payload", payload)

            result = asyncio.run(self.engine.execute({}, exec_mode))
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
                # Plain text - store directly so trigger sees a string
                payload = stripped

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

    # Set bundle path for VFS resolution and embedded plugin discovery
    if bundle_path:
        engine.set_bundle_path(bundle_path)

    # Start interactive shell
    repl = InteractiveREPL(
        engine=engine,
        protocol_path=protocol_path,
        verbose=verbose,
        show_logs=show_logs
    )

    repl.run()

    return 0
