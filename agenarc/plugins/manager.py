"""
Plugin Manager

Manages dynamic loading of operator plugins with hot reload support.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from agenarc.plugins.hot_loader import (
    HotPluginLoader,
    HotReloadConfig,
    PluginInfo,
    ReloadStrategy,
)

if TYPE_CHECKING:
    from agenarc.operators.operator import IOperator

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Manages plugin discovery, loading, and operator retrieval.

    Integrates with HotPluginLoader for automatic plugin reloading.

    Usage:
        manager = PluginManager(plugin_dirs=["~/.agenarc/plugins"])
        await manager.initialize()

        operator = manager.get_operator("my_plugin", "my_operator")
        operators = manager.list_operators()
    """

    def __init__(self, plugin_dirs: Optional[List[str]] = None, bundle_paths: Optional[List[Path]] = None):
        self._plugin_dirs = plugin_dirs or []
        self._bundle_paths = bundle_paths or []  # Bundle-embedded plugin directories
        self._operators: Dict[str, "IOperator"] = {}
        self._plugins: Dict[str, PluginInfo] = {}
        self._hot_loader: Optional[HotPluginLoader] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the plugin manager and start hot loading."""
        if self._initialized:
            return

        # Configure hot loader with global plugin directories
        config = HotReloadConfig(
            watch_paths=[Path(d).expanduser() for d in self._plugin_dirs],
            reload_strategy=ReloadStrategy.ATOMIC,
            debounce_ms=500,
        )

        self._hot_loader = HotPluginLoader(config)
        await self._hot_loader.initialize()

        # Discover embedded plugins from bundle directories
        await self._discover_bundle_plugins()

        # Register discovered plugins/operators locally
        for plugin_info in self._hot_loader.list_plugins():
            self._plugins[plugin_info.name] = plugin_info

        for op_key in self._hot_loader.list_operators():
            # Parse plugin.operator format
            parts = op_key.split(".", 1)
            if len(parts) == 2:
                self._operators[op_key] = self._hot_loader.get_operator(parts[0], parts[1])

        self._initialized = True
        logger.info(f"PluginManager initialized with {len(self._plugins)} plugins")

    async def _discover_bundle_plugins(self) -> None:
        """Discover embedded plugins from bundle directories."""
        for bundle_path in self._bundle_paths:
            plugins_dir = bundle_path / "plugins"
            if not plugins_dir.exists() or not plugins_dir.is_dir():
                continue

            # Scan for plugin directories within the bundle
            for item in plugins_dir.iterdir():
                if not item.is_dir():
                    continue
                agenarc_json = item / "agenarc.json"
                if agenarc_json.exists():
                    # Discover using hot loader's Python loader
                    if self._hot_loader and self._hot_loader._python_loader:
                        await self._hot_loader._python_loader.discover(
                            item, self._hot_loader._on_plugin_discovered
                        )

    def register_operator(
        self,
        plugin_name: str,
        function_name: str,
        operator: "IOperator"
    ) -> None:
        """
        Register an operator manually.

        Args:
            plugin_name: Name of the plugin
            function_name: Name of the function/operator
            operator: Operator instance
        """
        key = plugin_name if not function_name else f"{plugin_name}.{function_name}"
        self._operators[key] = operator

    def get_operator(
        self,
        plugin_name: str,
        function_name: str = ""
    ) -> Optional["IOperator"]:
        """
        Get an operator by plugin and function name.

        Args:
            plugin_name: Name of the plugin
            function_name: Name of the function/operator

        Returns:
            Operator instance or None
        """
        # Try local cache first
        key = f"{plugin_name}.{function_name}" if function_name else plugin_name
        if key in self._operators:
            return self._operators[key]

        # Try hot loader
        if self._hot_loader:
            op = self._hot_loader.get_operator(plugin_name, function_name)
            if op:
                self._operators[key] = op
                return op

        return None

    def list_operators(self) -> List[str]:
        """
        List all registered operator names.

        Returns:
            List of operator keys in "plugin.operator" format
        """
        return list(self._operators.keys())

    def list_plugins(self) -> List[PluginInfo]:
        """
        List all discovered plugins.

        Returns:
            List of PluginInfo objects
        """
        return list(self._plugins.values())

    def discover_plugins(self) -> None:
        """
        Discover plugins in configured directories.

        Note: This is called automatically during initialize().
        """
        # Discovery is handled by HotPluginLoader
        pass

    async def reload_plugin(self, plugin_name: str) -> bool:
        """
        Reload a specific plugin.

        Args:
            plugin_name: Name of plugin to reload

        Returns:
            True if successful
        """
        if not self._hot_loader:
            return False

        success = await self._hot_loader.reload_plugin(plugin_name)

        if success:
            # Refresh local operator cache for this plugin
            prefix = f"{plugin_name}."
            keys_to_remove = [k for k in self._operators if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._operators[key]

            # Re-register from hot loader
            for op_key in self._hot_loader.list_operators():
                if op_key.startswith(prefix):
                    parts = op_key.split(".", 1)
                    if len(parts) == 2:
                        self._operators[op_key] = self._hot_loader.get_operator(parts[0], parts[1])

        return success

    async def shutdown(self) -> None:
        """Shutdown the plugin manager and unload all plugins."""
        if self._hot_loader:
            await self._hot_loader.shutdown()

        self._operators.clear()
        self._plugins.clear()
        self._initialized = False

        logger.info("PluginManager shutdown complete")

    @property
    def hot_loader(self) -> Optional[HotPluginLoader]:
        """Get the hot plugin loader instance."""
        return self._hot_loader

    @property
    def is_initialized(self) -> bool:
        """Check if the manager is initialized."""
        return self._initialized
