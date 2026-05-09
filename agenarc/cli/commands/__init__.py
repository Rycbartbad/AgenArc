"""
Commands package for AgenArc CLI.

Each subcommand has its own module for maintainability.
Shared helpers used across commands are defined here.
All public symbols are re-exported for backward compatibility.
"""

import argparse
import asyncio
import code
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from agenarc import __version__
from agenarc.engine.executor import ExecutionEngine, ExecutionMode
from agenarc.engine.state import StateManager
from agenarc.operators.builtin import BUILTIN_OPERATORS
from agenarc.plugins.manager import PluginManager
from agenarc.protocol.loader import LoaderError, ProtocolLoader


def _install_bundle_plugins(bundle_path: Path, verbose: bool = False) -> None:
    """
    Install plugins from bundle's assets/plugins/ to global plugins directory.

    Args:
        bundle_path: Path to the agent bundle
        verbose: Print verbose output
    """
    import shutil

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
                    with open(target_meta, encoding="utf-8") as f:
                        target_version = json.load(f).get("version", "0")
                    with open(agenarc_json, encoding="utf-8") as f:
                        source_version = json.load(f).get("version", "0")
                    if target_version >= source_version:
                        if verbose:
                            print(f"Plugin '{plugin_dir.name}' already installed (v{target_version})")
                        continue
                except Exception as e:
                    logger.warning("Failed to read plugin versions: %s", e)

        # Copy plugin to global directory
        if verbose:
            print(f"Installing plugin '{plugin_dir.name}' to global plugins directory...")

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(plugin_dir, target_dir)


# Cache for extracted .agrc bundles: bundle_path -> extraction_dir
_agrc_cache: dict[Path, Path] = {}


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
    import tempfile
    import zipfile

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
        if item.is_dir() and (item / "flow.json").exists():
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
    if output_path.suffix != ".agrc":
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


def print_error(message: str) -> None:
    """Print error message to stderr."""
    print(f"ERROR: {message}", file=sys.stderr)


def print_success(message: str) -> None:
    """Print success message."""
    print(f"SUCCESS: {message}")


# --- Import command functions from sub-modules ---

from .info import command_info
from .pack import command_pack
from .run import command_run
from .serve import command_serve
from .shell import InteractiveREPL, command_shell
from .validate import command_validate
from .visualize import command_visualize
