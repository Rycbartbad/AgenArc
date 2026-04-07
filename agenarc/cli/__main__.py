"""
AgenArc CLI

Command-line interface for AgenArc execution engine.

Usage:
    agenarc run <agent.agrc|flow.json>
    agenarc validate <agent.agrc|flow.json>
    agenarc info <agent.agrc|flow.json>
    agenarc pack <directory> [output.agrc]
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
        Path to extracted bundle directory
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

    # Create engine with bundle path for embedded plugin discovery
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
    elif args.command == "pack":
        output = args.output or Path(str(args.source) + ".agrc")
        pack_bundle(args.source, output, args.verbose)
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
