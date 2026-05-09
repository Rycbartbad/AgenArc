"""
Command: serve — Start agent as a background service with event plugins.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from agenarc.engine.executor import ExecutionEngine, ExecutionMode
from agenarc.operators.builtin import BUILTIN_OPERATORS
from agenarc.plugins.manager import PluginManager
from agenarc.protocol.loader import LoaderError

from . import _install_bundle_plugins, _resolve_bundle_path, print_error

logger = logging.getLogger(__name__)


async def _start_event_plugins(
    engine: ExecutionEngine,
    plugin_manager: PluginManager,
    selected_plugins: list[str] | None = None,
    plugin_configs: dict[str, dict[str, Any]] | None = None,
) -> None:
    """
    Start event plugins and register them with the plugin manager.

    Event plugins are auto-detected from source nodes (nodes with no incoming edges)
    in the graph. Plugin nodes that are source nodes will be automatically loaded.

    Args:
        engine: Execution engine instance
        plugin_manager: Plugin manager instance
    """
    # Import event plugin base
    from agenarc.plugins.event_plugin import TriggerCallback

    # Create trigger callback
    trigger_callback = TriggerCallback(engine)
    trigger_callback.start()

    # Built-in event plugins
    built_in_plugins = {
        "qq": "agenarc.plugins.qq_plugin.plugin.QQ_Event_Plugin",
    }

    # Auto-detect source nodes (nodes with no incoming edges)
    source_nodes = engine._find_source_nodes()

    # For Plugin nodes that are source nodes, extract plugin info
    auto_detected_plugins = []
    for node in source_nodes:
        if node.type.value == "Plugin":
            # Extract plugin name from node config
            config = node.metadata.get("config", {})
            plugin_name = config.get("plugin", "")
            if plugin_name:
                auto_detected_plugins.append((node.id, plugin_name))

    # Load and start each detected plugin
    for _node_id, plugin_name in auto_detected_plugins:
        plugin_instance = None

        # 1) Try built-in plugin (e.g. qq)
        if plugin_name in built_in_plugins:
            try:
                class_path = built_in_plugins[plugin_name]
                module_path, class_name = class_path.rsplit(".", 1)
                import importlib as _il

                module = _il.import_module(module_path)
                plugin_class = getattr(module, class_name)
                plugin_instance = plugin_class()
            except Exception as e:
                print(f"[CLI] Failed to load built-in plugin '{plugin_name}': {e}")
                continue

        # 2) Try bundle-embedded plugin: scan plugins/ subdirs, read agenarc.json name field
        elif engine._bundle_path:
            plugins_root = engine._bundle_path / "plugins"
            if plugins_root.exists():
                import importlib.util as _util
                import json as _json

                found = False
                for subdir in plugins_root.iterdir():
                    if not subdir.is_dir():
                        continue
                    mp = subdir / "agenarc.json"
                    if not mp.exists():
                        continue
                    try:
                        with open(mp, encoding="utf-8") as f:
                            manifest = _json.load(f)
                    except Exception as e:
                        logger.warning("Failed to read plugin manifest %s: %s", mp, e)
                        continue
                    if manifest.get("name") != plugin_name:
                        continue
                    # Match by agenarc.json name field
                    found = True
                    entry = manifest.get("entry", "plugin.py")
                    ops = manifest.get("operators", [])
                    if not ops:
                        print(f"[CLI] Plugin '{plugin_name}' has no operators in manifest")
                        break
                    entry_path = subdir / entry
                    if not entry_path.exists():
                        print(f"[CLI] Plugin '{plugin_name}' entry not found: {entry_path}")
                        break
                    spec = _util.spec_from_file_location(f"_bundle_plugin_{plugin_name}", entry_path)
                    if spec is None or spec.loader is None:
                        print(f"[CLI] Failed to create module spec for '{plugin_name}'")
                        break
                    module = _util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    # operators can be strings or dicts (dict has "name" field)
                    first_op = ops[0]
                    op_name = first_op if isinstance(first_op, str) else first_op.get("name")
                    if not op_name:
                        print(f"[CLI] Plugin '{plugin_name}' has no valid operator name")
                        break
                    plugin_class = getattr(module, op_name)
                    plugin_instance = plugin_class()
                    break
                if not found:
                    print(f"[CLI] Unknown event plugin '{plugin_name}' — not found in bundle plugins/")
                    continue

        if plugin_instance is None:
            continue

        # Build plugin configuration from config.yaml: plugins.<name>.*
        plugin_cfg = {}
        try:
            from agenarc.config import get_config

            config = get_config()
            file_config = config.get(f"plugins.{plugin_name}", {})
            if file_config:
                plugin_cfg.update(file_config)
        except Exception as e:
            logger.warning("Failed to read plugin config for %s: %s", plugin_name, e)

        if hasattr(plugin_instance, "configure"):
            plugin_instance.configure(plugin_cfg)

        # Register with plugin manager
        plugin_manager.register_event_plugin(plugin_name, plugin_instance)

        # Start the plugin
        await plugin_manager.start_event_plugin(plugin_name, trigger_callback)

    # Store callback reference to prevent garbage collection
    setattr(engine, "_event_trigger_callback", trigger_callback)  # noqa: B010


def command_serve(file: Path, mode: str = "async", verbose: bool = False) -> int:
    """
    Start agent as a background service with event plugins.

    Plugins are auto-detected from source nodes (Plugin nodes with no incoming edges).

    Args:
        file: Path to agent bundle (.agrc) or protocol (.json)
        mode: Execution mode
        verbose: Verbose output flag

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

    # Create engine with bundle path for embedded plugin discovery
    import agenarc

    package_plugins_dir = str(Path(agenarc.__file__).parent / "plugins")
    plugin_manager = PluginManager(plugin_dirs=[package_plugins_dir], bundle_paths=[bundle_path] if bundle_path else [])
    engine = ExecutionEngine(plugin_manager=plugin_manager)

    # Register built-in operators
    for node_type, operator_class in BUILTIN_OPERATORS.items():
        if operator_class is not None:
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

    # Set bundle path for VFS resolution and embedded plugin discovery
    if bundle_path:
        engine.set_bundle_path(bundle_path)

    # Choose execution mode
    {"sync": ExecutionMode.SYNC, "async": ExecutionMode.ASYNC, "parallel": ExecutionMode.PARALLEL}.get(
        mode, ExecutionMode.ASYNC
    )

    # Create event loop and start event plugins
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Set up signal handlers for graceful shutdown
    stop_event = asyncio.Event()
    shutdown_done = asyncio.Event()

    def signal_handler(sig, frame):
        """Handle Ctrl+C by setting stop event."""
        import sys

        stop_event.set()
        loop.call_soon(loop.stop)
        sys.stdout.flush()
        sys.stderr.flush()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    async def run_service():
        """Run the service with event plugins."""
        print("[CLI] AgenArc service started.", flush=True)

        # Initialize plugin manager to discover operators
        await plugin_manager.initialize()

        await _start_event_plugins(engine, plugin_manager)

        # Wait for stop signal
        await stop_event.wait()
        shutdown_done.set()

    # Track shutdown completion
    shutdown_complete = False

    async def shutdown_with_timeout():
        """Perform shutdown with guaranteed timeout."""
        nonlocal shutdown_complete
        if shutdown_complete:
            return
        shutdown_complete = True

        # Force stop event
        stop_event.set()

        # Stop all event plugins
        try:
            await asyncio.wait_for(plugin_manager.stop_all_event_plugins(), timeout=5.0)
        except TimeoutError:
            logger.warning("Timeout stopping event plugins during shutdown")
        except Exception as e:
            logger.warning("Failed to stop event plugins: %s", e)

        # Shutdown plugin manager
        try:
            await asyncio.wait_for(plugin_manager.shutdown(), timeout=5.0)
        except TimeoutError:
            logger.warning("Timeout shutting down plugin manager")
        except Exception as e:
            logger.warning("Failed to shutdown plugin manager: %s", e)

        shutdown_done.set()

    try:
        loop.run_until_complete(run_service())
    except (KeyboardInterrupt, RuntimeError):
        if not shutdown_complete:
            loop.run_until_complete(shutdown_with_timeout())
    finally:
        import sys

        sys.stdout.flush()
        sys.stderr.flush()
        if not loop.is_closed():
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    return 0
