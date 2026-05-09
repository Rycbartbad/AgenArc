"""
Command: info — Show agent/protocol information.
"""

import json
import logging
from pathlib import Path

from agenarc.protocol.loader import ProtocolLoader, LoaderError

from . import _resolve_bundle_path, print_error

logger = logging.getLogger(__name__)


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
            except Exception as e:
                logger.warning("Failed to load manifest: %s", e)

        print(f"AgenArc Protocol Information")
        print(f"=" * 40)
        print(f"Version: {graph.version}")
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
