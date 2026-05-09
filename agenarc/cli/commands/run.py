"""
Command: run — Execute an agent bundle or protocol file.
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

from agenarc.engine.executor import ExecutionEngine, ExecutionMode
from agenarc.operators.builtin import BUILTIN_OPERATORS
from agenarc.plugins.manager import PluginManager
from agenarc.protocol.loader import ProtocolLoader, LoaderError

from . import _resolve_bundle_path, _install_bundle_plugins, print_error, print_success


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

    # Set bundle path for VFS resolution
    if bundle_path:
        engine.set_bundle_path(bundle_path)

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
