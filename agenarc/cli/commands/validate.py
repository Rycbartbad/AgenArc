"""
Command: validate — Validate an agent bundle or protocol file.
"""

from pathlib import Path

from agenarc.protocol.loader import LoaderError, ProtocolLoader

from . import _resolve_bundle_path, print_error, print_success


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

        print_success("Protocol is valid")
        print(f"  Version: {graph.version}")
        print(f"  Nodes: {len(graph.nodes)}")
        print(f"  Edges: {len(graph.edges)}")

        return 0

    except LoaderError as e:
        print_error(f"Validation failed: {e}")
        return 1
