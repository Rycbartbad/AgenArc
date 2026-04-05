"""
AgenArc CLI

Command-line interface for AgenArc execution engine.

Usage:
    python -m agenarc run <protocol.json>
    python -m agenarc validate <protocol.json>
    python -m agenarc info <protocol.json>
"""

import argparse
import asyncio
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
        help="Execute a protocol file"
    )
    run_parser.add_argument(
        "file",
        type=Path,
        help="Path to protocol JSON file"
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

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a protocol file"
    )
    validate_parser.add_argument(
        "file",
        type=Path,
        help="Path to protocol JSON file"
    )

    # info command
    info_parser = subparsers.add_parser(
        "info",
        help="Show protocol information"
    )
    info_parser.add_argument(
        "file",
        type=Path,
        help="Path to protocol JSON file"
    )

    return parser


def print_error(message: str) -> None:
    """Print error message to stderr."""
    print(f"ERROR: {message}", file=sys.stderr)


def print_success(message: str) -> None:
    """Print success message."""
    print(f"SUCCESS: {message}")


def command_run(
    file: Path,
    input_json: Optional[str] = None,
    mode: str = "async",
    verbose: bool = False
) -> int:
    """
    Execute a protocol file.

    Args:
        file: Path to protocol file
        input_json: Initial input as JSON string
        mode: Execution mode
        verbose: Verbose output flag

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse initial inputs
    initial_inputs = {}
    if input_json:
        try:
            initial_inputs = json.loads(input_json)
        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON in --input: {e}")
            return 1

    # Create engine
    plugin_manager = PluginManager()
    engine = ExecutionEngine(plugin_manager=plugin_manager)

    # Register built-in operators
    for node_type, operator_class in BUILTIN_OPERATORS.items():
        engine.register_builtin_operator(node_type, operator_class)

    # Load protocol
    if verbose:
        print(f"Loading protocol from {file}...")

    try:
        engine.load_protocol(file)
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
    Validate a protocol file.

    Args:
        file: Path to protocol file

    Returns:
        Exit code (0 for valid, 1 for invalid)
    """
    try:
        loader = ProtocolLoader(validate=True)
        graph = loader.load(file)

        print_success(f"Protocol is valid")
        print(f"  Version: {graph.version}")
        print(f"  Entry Point: {graph.entryPoint}")
        print(f"  Nodes: {len(graph.nodes)}")
        print(f"  Edges: {len(graph.edges)}")

        return 0

    except LoaderError as e:
        print_error(f"Validation failed: {e}")
        return 1


def command_info(file: Path) -> int:
    """
    Show protocol information.

    Args:
        file: Path to protocol file

    Returns:
        Exit code
    """
    try:
        loader = ProtocolLoader(validate=False)
        graph = loader.load(file)

        print(f"AgenArc Protocol Information")
        print(f"=" * 40)
        print(f"Version: {graph.version}")
        print(f"Entry Point: {graph.entryPoint}")

        if graph.metadata.name:
            print(f"Name: {graph.metadata.name}")
        if graph.metadata.description:
            print(f"Description: {graph.metadata.description}")
        if graph.metadata.author:
            print(f"Author: {graph.metadata.author}")

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
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
