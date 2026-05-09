"""
Command: visualize — Start visualization studio for agent editing and debugging.
"""

import asyncio
import logging
import webbrowser
from pathlib import Path

from agenarc.engine.executor import ExecutionEngine
from agenarc.operators.builtin import BUILTIN_OPERATORS
from agenarc.plugins.manager import PluginManager
from agenarc.protocol.loader import LoaderError

from . import _install_bundle_plugins, _resolve_bundle_path, print_error

logger = logging.getLogger(__name__)


def command_visualize(
    file: Path, host: str = "127.0.0.1", port: int = 8765, mode: str = "async", verbose: bool = False
) -> int:
    """
    Start visualization studio for agent editing and debugging.

    Args:
        file: Path to agent bundle (.agrc) or protocol (.json)
        host: Host to bind the visualization server
        port: Port for the visualization server
        mode: Execution mode
        verbose: Verbose output flag

    Returns:
        Exit code
    """
    from agenarc.visualization.server import VisualizationServer

    # Resolve bundle path
    protocol_path = _resolve_bundle_path(file)

    # Determine bundle path
    bundle_path = None
    if protocol_path.is_dir():
        bundle_path = protocol_path
        _install_bundle_plugins(bundle_path, verbose)

    # Create engine with global + package plugin directories
    import agenarc

    package_plugins_dir = str(Path(agenarc.__file__).parent / "plugins")
    global_plugins_dir = str(Path("~/.agenarc/plugins").expanduser())
    plugin_manager = PluginManager(
        plugin_dirs=[global_plugins_dir, package_plugins_dir], bundle_paths=[bundle_path] if bundle_path else []
    )
    engine = ExecutionEngine(plugin_manager=plugin_manager)

    # Register built-in operators
    for node_type, operator_class in BUILTIN_OPERATORS.items():
        if operator_class:
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

    # Initialize plugin manager and create visualization server
    try:
        asyncio.run(plugin_manager.initialize())
    except Exception as e:
        logger.warning("Plugin initialization failed: %s", e)
        if verbose:
            print("Warning: Plugin initialization failed, some plugins may not be available")

    bundle_path_str = str(bundle_path) if bundle_path else None
    server = VisualizationServer(
        engine=engine,
        host=host,
        port=port,
        bundle_path=bundle_path_str,
        protocol_path=str(protocol_path),
    )

    if verbose:
        print(f"Starting visualization server at http://{host}:{port}")

    # Run server — single event loop for both start and stop
    async def _run_visualize():
        try:
            await server.start()
            webbrowser.open(f"http://{host}:{port}")
        except asyncio.CancelledError:
            logger.debug("Visualization server task cancelled")
        finally:
            await server.stop()

    try:
        asyncio.run(_run_visualize())
    except KeyboardInterrupt:
        logger.debug("Visualization server stopped by user (Ctrl+C)")

    return 0
