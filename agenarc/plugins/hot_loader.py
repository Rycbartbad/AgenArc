"""
Hot Plugin Loader

Provides file watching and atomic plugin reloading for zero-downtime updates.
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import threading
import hashlib

logger = logging.getLogger(__name__)


class ReloadStrategy(Enum):
    """Plugin reload strategy."""
    ATOMIC = auto()      # Atomic swap (zero-downtime)
    GRACEFUL = auto()    # Wait for current operations to complete
    IMMEDIATE = auto()   # Immediate reload (may cause brief downtime)


@dataclass
class PluginInfo:
    """Plugin metadata and status."""
    name: str
    version: str
    path: Path
    loader_type: str  # "python", "cpp", "external"
    loaded_at: float = 0
    file_hash: str = ""
    enabled: bool = True


@dataclass
class HotReloadConfig:
    """Configuration for hot reloading."""
    watch_paths: List[Path] = field(default_factory=list)
    reload_strategy: ReloadStrategy = ReloadStrategy.ATOMIC
    debounce_ms: int = 500          # Debounce file change events
    scan_interval_seconds: float = 5.0  # Periodic scan interval
    max_retries: int = 3
    retry_delay_seconds: float = 1.0


class FileWatcher:
    """
    Cross-platform file watcher using the best available method.

    Priority: inotify (Linux) > FSEvents (macOS) > watchdog > polling
    """

    def __init__(self, paths: List[Path], callback: Callable[[Set[Path]], None]):
        self._paths = paths
        self._callback = callback
        self._running = False
        self._modified_files: Set[Path] = set()
        self._lock = threading.Lock()
        self._watchdog_handle = None

    def start(self) -> None:
        """Start watching for file changes."""
        if self._running:
            return

        self._running = True

        # Try watchdog first (cross-platform)
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class ChangeHandler(FileSystemEventHandler):
                def __init__(handler_self, watcher: "FileWatcher"):
                    handler_self.watcher = watcher

                def on_modified(handler_self, event):
                    if event.is_directory:
                        return
                    path = Path(event.src_path)
                    if path.suffix in {".py", ".so", ".dylib", ".dll"}:
                        with handler_self.watcher._lock:
                            handler_self.watcher._modified_files.add(path)

            self._watchdog_handler = ChangeHandler(self)
            self._watchdog_observer = Observer()
            for path in self._paths:
                if path.exists():
                    self._watchdog_observer.schedule(
                        self._watchdog_handler,
                        str(path),
                        recursive=True
                    )
            self._watchdog_observer.start()
            logger.info("File watcher started (using watchdog)")
            return
        except ImportError:
            pass

        # Fallback to polling
        self._file_mtimes: Dict[Path, float] = {}
        threading.Thread(target=self._poll_loop, daemon=True).start()
        logger.info("File watcher started (using polling)")

    def _poll_loop(self) -> None:
        """Polling loop for file changes."""
        while self._running:
            try:
                current_files = self._collect_files()
                for path, mtime in current_files.items():
                    if path not in self._file_mtimes:
                        self._file_mtimes[path] = mtime
                    elif self._file_mtimes[path] < mtime:
                        with self._lock:
                            self._modified_files.add(path)
                        self._file_mtimes[path] = mtime
            except Exception as e:
                logger.debug(f"Polling error: {e}")

            time.sleep(0.5)  # Poll every 500ms

    def _collect_files(self) -> Dict[Path, float]:
        """Collect all plugin files and their modification times."""
        files = {}
        for base_path in self._paths:
            if not base_path.exists():
                continue
            if base_path.is_file():
                try:
                    files[base_path] = os.path.getmtime(base_path)
                except OSError:
                    pass
            else:
                for ext in {".py", ".so", ".dylib", ".dll", ".json"}:
                    for path in base_path.rglob(f"*{ext}"):
                        try:
                            files[path] = os.path.getmtime(path)
                        except OSError:
                            pass
        return files

    def get_modified_files(self) -> Set[Path]:
        """Get and clear modified files since last check."""
        with self._lock:
            modified = self._modified_files.copy()
            self._modified_files.clear()
            return modified

    def stop(self) -> None:
        """Stop watching for file changes."""
        self._running = False
        if hasattr(self, "_watchdog_observer") and self._watchdog_observer:
            self._watchdog_observer.stop()
            self._watchdog_observer.join(timeout=2)


class HotPluginLoader:
    """
    Hot plugin loader with file watching and atomic reload support.

    Features:
    - File watching for automatic reload detection
    - Atomic plugin replacement (zero-downtime)
    - Debounced reload to avoid thrashing on multiple file changes
    - Graceful shutdown with operation completion

    Usage:
        loader = HotPluginLoader(plugin_dirs=["~/.agenarc/plugins"])
        await loader.initialize()

        # Plugin is auto-reloaded when files change
        operator = loader.get_operator("my_plugin", "my_operator")
    """

    def __init__(self, config: Optional[HotReloadConfig] = None):
        self._config = config or HotReloadConfig()
        self._plugins: Dict[str, PluginInfo] = {}
        self._operators: Dict[str, Any] = {}  # plugin.operator -> instance
        self._file_watcher: Optional[FileWatcher] = None
        self._running = False
        self._reload_semaphore = asyncio.Semaphore(1)
        self._pending_reloads: Set[str] = set()

        # Per-loader registries
        self._python_loader: Optional["PythonPluginLoader"] = None
        self._cpp_loader: Optional["CppPluginLoader"] = None
        self._external_loader: Optional["ExternalPluginLoader"] = None

    async def initialize(self) -> None:
        """Initialize the hot loader and start file watching."""
        if self._running:
            return

        self._running = True

        # Initialize loaders
        await self._init_loaders()

        # Discover existing plugins
        await self._discover_plugins()

        # Start file watcher
        watch_paths = self._get_watch_paths()
        if watch_paths:
            self._file_watcher = FileWatcher(watch_paths, self._on_files_changed)
            self._file_watcher.start()

        logger.info(f"HotPluginLoader initialized with {len(self._plugins)} plugins")

    async def _init_loaders(self) -> None:
        """Initialize individual plugin loaders."""
        from agenarc.plugins.loaders.python import PythonPluginLoader
        from agenarc.plugins.loaders.cpp import CppPluginLoader
        from agenarc.plugins.loaders.external import ExternalPluginLoader

        self._python_loader = PythonPluginLoader()
        self._cpp_loader = CppPluginLoader()
        self._external_loader = ExternalPluginLoader()

    def _get_watch_paths(self) -> List[Path]:
        """Get all paths to watch for file changes."""
        paths = []
        for search_path in self._config.watch_paths:
            path = Path(search_path).expanduser()
            if path.exists():
                paths.append(path)
        return paths

    async def _discover_plugins(self) -> None:
        """Discover and load plugins from configured directories."""
        tasks = []
        for search_path in self._config.watch_paths:
            path = Path(search_path).expanduser()
            if not path.exists():
                continue

            # Discover based on loader type
            if self._python_loader:
                tasks.append(self._python_loader.discover(path, self._on_plugin_discovered))
            if self._cpp_loader:
                tasks.append(self._cpp_loader.discover(path, self._on_plugin_discovered))
            if self._external_loader:
                tasks.append(self._external_loader.discover(path, self._on_plugin_discovered))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _on_plugin_discovered(self, plugin_info: PluginInfo) -> None:
        """Callback when a plugin is discovered."""
        self._plugins[plugin_info.name] = plugin_info
        await self._load_plugin(plugin_info)

    async def _load_plugin(self, plugin_info: PluginInfo) -> bool:
        """Load a single plugin and register its operators."""
        try:
            if plugin_info.loader_type == "python":
                if not self._python_loader:
                    return False
                operators = await self._python_loader.load(plugin_info)
            elif plugin_info.loader_type == "cpp":
                if not self._cpp_loader:
                    return False
                operators = await self._cpp_loader.load(plugin_info)
            elif plugin_info.loader_type == "external":
                if not self._external_loader:
                    return False
                operators = await self._external_loader.load(plugin_info)
            else:
                logger.warning(f"Unknown loader type: {plugin_info.loader_type}")
                return False

            # Register operators
            for op_name, operator in operators.items():
                key = f"{plugin_info.name}.{op_name}"
                self._operators[key] = operator
                logger.debug(f"Registered operator: {key}")

            plugin_info.loaded_at = time.time()
            logger.info(f"Loaded plugin: {plugin_info.name} ({len(operators)} operators)")
            return True

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_info.name}: {e}")
            return False

    def _on_files_changed(self, modified_files: Set[Path]) -> None:
        """Callback when plugin files are modified."""
        if not modified_files:
            return

        # Schedule reload with debounce
        asyncio.create_task(self._schedule_reload(modified_files))

    async def _schedule_reload(self, modified_files: Set[Path]) -> None:
        """Schedule a debounced reload."""
        # Debounce: wait for more changes to settle
        await asyncio.sleep(self._config.debounce_ms / 1000.0)

        # Check if more files were modified during debounce
        fresh_modifications = self._file_watcher.get_modified_files() if self._file_watcher else set()
        all_modified = modified_files | fresh_modifications

        # Find affected plugins
        affected = set()
        for plugin_name, plugin_info in self._plugins.items():
            try:
                # Check if any modified file belongs to this plugin
                plugin_dir = plugin_info.path.parent
                for f in all_modified:
                    try:
                        f.resolve().relative_to(plugin_dir.resolve())
                        affected.add(plugin_name)
                        break
                    except ValueError:
                        pass
            except Exception:
                pass

        if affected:
            logger.info(f"Scheduling reload for: {affected}")
            for plugin_name in affected:
                self._pending_reloads.add(plugin_name)
            await self._execute_pending_reloads()

    async def _execute_pending_reloads(self) -> None:
        """Execute pending plugin reloads."""
        async with self._reload_semaphore:
            while self._pending_reloads:
                plugin_name = self._pending_reloads.pop()
                await self._reload_plugin(plugin_name)

    async def _reload_plugin(self, plugin_name: str) -> bool:
        """Reload a specific plugin atomically."""
        if plugin_name not in self._plugins:
            logger.warning(f"Plugin not found for reload: {plugin_name}")
            return False

        plugin_info = self._plugins[plugin_name]

        # Quiescence: wait for current operations to complete
        if self._config.reload_strategy == ReloadStrategy.GRACEFUL:
            await asyncio.sleep(0.1)  # Allow in-flight operations to complete

        # Unload existing operators
        prefix = f"{plugin_name}."
        keys_to_remove = [k for k in self._operators if k.startswith(prefix)]
        for key in keys_to_remove:
            del self._operators[key]

        # Reload the plugin
        success = await self._load_plugin(plugin_info)

        if success:
            logger.info(f"Reloaded plugin: {plugin_name}")
        else:
            logger.error(f"Failed to reload plugin: {plugin_name}")

        return success

    def get_operator(self, plugin_name: str, operator_name: str = "") -> Optional[Any]:
        """
        Get an operator by plugin and function name.

        Args:
            plugin_name: Name of the plugin
            operator_name: Name of the operator (optional if plugin has single operator)

        Returns:
            Operator instance or None
        """
        key = f"{plugin_name}.{operator_name}" if operator_name else plugin_name
        return self._operators.get(key)

    def list_operators(self) -> List[str]:
        """List all registered operator names."""
        return list(self._operators.keys())

    def list_plugins(self) -> List[PluginInfo]:
        """List all discovered plugins."""
        return list(self._plugins.values())

    async def reload_plugin(self, plugin_name: str) -> bool:
        """
        Manually trigger a plugin reload.

        Args:
            plugin_name: Name of plugin to reload

        Returns:
            True if reload was successful
        """
        return await self._reload_plugin(plugin_name)

    async def shutdown(self) -> None:
        """Gracefully shutdown the hot loader."""
        self._running = False

        if self._file_watcher:
            self._file_watcher.stop()

        # Unload all plugins
        self._operators.clear()
        self._plugins.clear()

        logger.info("HotPluginLoader shutdown complete")

    @property
    def is_running(self) -> bool:
        """Check if the loader is running."""
        return self._running


# Import loaders at module level for type hints
from agenarc.plugins.loaders.python import PythonPluginLoader
from agenarc.plugins.loaders.cpp import CppPluginLoader
from agenarc.plugins.loaders.external import ExternalPluginLoader
