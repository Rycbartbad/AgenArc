"""
Cpp Plugin Loader

Loads C++ compiled plugins via ctypes/Foreign Function Interface.
"""

import asyncio
import ctypes
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CppPluginLoader:
    """
    Loads C++ compiled plugins using ctypes.

    Plugin structure:
        plugin_name/
        ├── agenarc.json     # Plugin manifest
        └── libplugin.so     # Compiled shared library

    agenarc.json format:
        {
            "name": "plugin_name",
            "version": "1.0.0",
            "library": "libplugin.so",
            "symbols": ["create_operator_1", "create_operator_2"]
        }

    C++ plugin must export:
        extern "C" {
            void* create_<operator_name>(void* context);
            void destroy_<operator_name>(void* operator);
        }
    """

    def __init__(self):
        self._libraries: Dict[str, ctypes.CDLL] = {}
        self._factories: Dict[str, Any] = {}

    def _get_library_extension(self) -> str:
        """Get platform-specific library extension."""
        if sys.platform == "win32":
            return ".dll"
        elif sys.platform == "darwin":
            return ".dylib"
        else:
            return ".so"

    async def discover(
        self,
        search_path: Path,
        callback: Callable[[Any], None]
    ) -> List[str]:
        """
        Discover C++ plugins in a directory.

        Args:
            search_path: Directory to search
            callback: Called with each discovered PluginInfo

        Returns:
            List of discovered plugin names
        """
        discovered = []

        if not search_path.exists():
            return discovered

        lib_ext = self._get_library_extension()

        # Look for directories with agenarc.json and .so/.dll/.dylib
        for item in search_path.iterdir():
            if not item.is_dir():
                continue

            manifest_path = item / "agenarc.json"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                lib_name = manifest.get("library", f"lib{item.name}{lib_ext}")
                lib_path = item / lib_name

                if not lib_path.exists():
                    logger.debug(f"C++ library not found: {lib_path}")
                    continue

                from agenarc.plugins.hot_loader import PluginInfo

                plugin_info = PluginInfo(
                    name=manifest.get("name", item.name),
                    version=manifest.get("version", "1.0.0"),
                    path=lib_path,
                    loader_type="cpp",
                )

                await callback(plugin_info)
                discovered.append(plugin_info.name)

            except Exception as e:
                logger.debug(f"Failed to load plugin manifest {manifest_path}: {e}")

        return discovered

    async def load(self, plugin_info: Any) -> Dict[str, Any]:
        """
        Load a C++ plugin and return its operators.

        Args:
            plugin_info: PluginInfo object

        Returns:
            Dict mapping operator names to wrapper instances
        """
        lib_path = plugin_info.path

        # Load manifest
        manifest_path = lib_path.parent / "agenarc.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Load the shared library
        try:
            library = ctypes.CDLL(str(lib_path))
            self._libraries[plugin_info.name] = library
        except Exception as e:
            logger.error(f"Failed to load C++ library {lib_path}: {e}")
            return {}

        # Get factory symbols
        operators = {}
        symbols = manifest.get("symbols", [])

        for symbol_name in symbols:
            factory_name = f"create_{symbol_name}"
            destructor_name = f"destroy_{symbol_name}"

            if hasattr(library, factory_name):
                try:
                    factory = getattr(library, factory_name)
                    factory.restype = ctypes.c_void_p

                    # Create operator wrapper
                    operator_ptr = factory()

                    wrapper = CppOperatorWrapper(
                        library=library,
                        destructor_name=destructor_name,
                        operator_ptr=operator_ptr,
                        symbol_name=symbol_name,
                    )
                    operators[symbol_name] = wrapper

                    logger.debug(f"Loaded C++ operator: {symbol_name}")

                except Exception as e:
                    logger.error(f"Failed to load operator {symbol_name}: {e}")

        return operators

    def unload(self, plugin_name: str) -> bool:
        """
        Unload a C++ plugin library.

        Args:
            plugin_name: Name of plugin to unload

        Returns:
            True if successful
        """
        if plugin_name in self._libraries:
            try:
                # Close the library
                handle = self._libraries[plugin_name]._handle
                if sys.platform == "win32":
                    ctypes.windll.kernel32.FreeLibrary(handle)
                else:
                    ctypes.cdll.dlclose(handle)
            except Exception as e:
                logger.error(f"Failed to unload library: {e}")

            del self._libraries[plugin_name]
            return True
        return False


class CppOperatorWrapper:
    """
    Wrapper for C++ operators loaded via ctypes.

    Provides a Python interface to C++ operator implementations.
    """

    def __init__(
        self,
        library: ctypes.CDLL,
        destructor_name: str,
        operator_ptr: int,
        symbol_name: str,
    ):
        self._library = library
        self._destructor_name = destructor_name
        self._operator_ptr = operator_ptr
        self._symbol_name = symbol_name
        self._destroyed = False

    def call_method(self, method_name: str, *args) -> Any:
        """
        Call a method on the C++ operator.

        Args:
            method_name: Name of the method to call
            *args: Arguments to pass

        Returns:
            Result from C++ method
        """
        if self._destroyed:
            raise RuntimeError("Operator has been destroyed")

        # Look for method in library
        full_name = f"{self._symbol_name}_{method_name}"
        if hasattr(self._library, full_name):
            method = getattr(self._library, full_name)
            return method(self._operator_ptr, *args)

        raise AttributeError(f"Method not found: {method_name}")

    def __del__(self):
        """Destructor - release C++ resources."""
        if not self._destroyed and hasattr(self._library, self._destructor_name):
            try:
                destructor = getattr(self._library, self._destructor_name)
                destructor(self._operator_ptr)
            except Exception:
                pass
        self._destroyed = True
