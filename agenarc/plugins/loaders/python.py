"""
Python Plugin Loader

Dynamically loads Python-based plugins using importlib.
"""

import asyncio
import importlib
import importlib.util
import logging
import os
import sys
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PythonPluginLoader:
    """
    Loads Python-based plugins using importlib.

    Plugin structure:
        plugin_name/
        ├── agenarc.json     # Plugin manifest
        └── plugin.py        # Plugin implementation

    agenarc.json format:
        {
            "name": "plugin_name",
            "version": "1.0.0",
            "entry": "plugin.py",
            "operators": ["op1", "op2"]
        }
    """

    def __init__(self):
        self._plugins: Dict[str, Any] = {}  # module cache

    async def discover(
        self,
        search_path: Path,
        callback: Callable[[Any], None]
    ) -> List[str]:
        """
        Discover Python plugins in a directory.

        Args:
            search_path: Directory to search
            callback: Called with each discovered PluginInfo

        Returns:
            List of discovered plugin names
        """
        discovered = []

        if not search_path.exists():
            return discovered

        # Look for directories with agenarc.json
        for item in search_path.iterdir():
            if not item.is_dir():
                continue

            manifest_path = item / "agenarc.json"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                from agenarc.plugins.hot_loader import PluginInfo

                plugin_info = PluginInfo(
                    name=manifest.get("name", item.name),
                    version=manifest.get("version", "1.0.0"),
                    path=manifest_path,
                    loader_type="python",
                )

                await callback(plugin_info)
                discovered.append(plugin_info.name)

            except Exception as e:
                logger.debug(f"Failed to load plugin manifest {manifest_path}: {e}")

        return discovered

    async def load(self, plugin_info: Any) -> Dict[str, Any]:
        """
        Load a Python plugin and return its operators.

        Args:
            plugin_info: PluginInfo object

        Returns:
            Dict mapping operator names to instances
        """
        manifest_path = plugin_info.path
        plugin_dir = manifest_path.parent

        # Load manifest to get entry point
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        entry_file = manifest.get("entry", "plugin.py")
        module_name = manifest.get("name", plugin_dir.name)

        # Build module path
        plugin_file = plugin_dir / entry_file
        if not plugin_file.exists():
            logger.error(f"Plugin entry file not found: {plugin_file}")
            return {}

        # Load module dynamically
        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create module spec for {plugin_file}")
                return {}

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            self._plugins[plugin_info.name] = module

        except Exception as e:
            logger.error(f"Failed to load plugin module {plugin_file}: {e}")
            return {}

        # Extract operators
        operators = {}
        operator_names = manifest.get("operators", [])

        for op_name in operator_names:
            if hasattr(module, op_name):
                op_class = getattr(module, op_name)
                try:
                    # Instantiate operator
                    operator = op_class()
                    operators[op_name] = operator
                except Exception as e:
                    logger.error(f"Failed to instantiate operator {op_name}: {e}")

        # Also look for any IOperator subclasses in the module
        from agenarc.operators.operator import IOperator
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, IOperator) and attr is not IOperator:
                if attr_name not in operators:
                    try:
                        operators[attr_name] = attr()
                    except Exception as e:
                        logger.error(f"Failed to instantiate {attr_name}: {e}")

        return operators

    def unload(self, plugin_name: str) -> bool:
        """
        Unload a plugin module.

        Args:
            plugin_name: Name of plugin to unload

        Returns:
            True if successful
        """
        if plugin_name in self._plugins:
            # Remove from sys.modules
            module = self._plugins[plugin_name]
            module_name = module.__name__
            if module_name in sys.modules:
                del sys.modules[module_name]
            del self._plugins[plugin_name]
            return True
        return False

    def get_plugin(self, plugin_name: str) -> Optional[Any]:
        """Get a loaded plugin module."""
        return self._plugins.get(plugin_name)
