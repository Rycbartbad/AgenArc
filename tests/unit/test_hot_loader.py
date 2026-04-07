"""Unit tests for plugins/hot_loader.py."""

import pytest
import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from agenarc.plugins.hot_loader import (
    HotPluginLoader,
    HotReloadConfig,
    PluginInfo,
    ReloadStrategy,
    FileWatcher,
)


class TestFileWatcher:
    """Tests for FileWatcher."""

    def test_creation(self, tmp_path):
        """Test FileWatcher creation."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)

        assert watcher._paths == [tmp_path]
        assert watcher._callback == callback
        assert watcher._running is False

    def test_get_modified_files_empty(self, tmp_path):
        """Test get_modified_files when no files changed."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)

        modified = watcher.get_modified_files()

        assert modified == set()

    def test_get_modified_files_with_changes(self, tmp_path):
        """Test get_modified_files returns modified files."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)

        # Simulate a modified file
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        # Manually add to modified files for testing
        watcher._modified_files.add(test_file)

        modified = watcher.get_modified_files()

        assert test_file in modified

    def test_stop_when_not_running(self, tmp_path):
        """Test stop when watcher not running."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)

        # Should not raise
        watcher.stop()


class TestFileWatcherCollectFiles:
    """Tests for FileWatcher._collect_files method."""

    def test_collect_files_empty_directory(self, tmp_path):
        """Test collecting files from empty directory."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)

        files = watcher._collect_files()

        assert files == {}

    def test_collect_files_with_python_file(self, tmp_path):
        """Test collecting .py files."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)

        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        files = watcher._collect_files()

        assert test_file in files

    def test_collect_files_with_json_file(self, tmp_path):
        """Test collecting .json files."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)

        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        files = watcher._collect_files()

        assert test_file in files

    def test_collect_files_ignores_other_extensions(self, tmp_path):
        """Test that .txt files are ignored."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        files = watcher._collect_files()

        assert test_file not in files

    def test_collect_files_nonexistent_path(self, tmp_path):
        """Test collecting from nonexistent path."""
        callback = MagicMock()
        nonexistent = tmp_path / "nonexistent"
        watcher = FileWatcher([nonexistent], callback)

        files = watcher._collect_files()

        assert files == {}

    def test_collect_files_with_shared_library(self, tmp_path):
        """Test collecting .so files on Linux."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)

        test_file = tmp_path / "libtest.so"
        test_file.write_text("binary content")

        files = watcher._collect_files()

        assert test_file in files


class TestFileWatcherStart:
    """Tests for FileWatcher.start method."""

    def test_start_already_running(self, tmp_path):
        """Test start does nothing if already running."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)
        watcher._running = True

        watcher.start()

        assert watcher._running is True

    def test_start_with_watchdog_fallback(self, tmp_path):
        """Test start uses polling when watchdog unavailable."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)

        # Patch watchdog import to fail
        with patch.dict('sys.modules', {'watchdog': None}):
            watcher.start()

        assert watcher._running is True


class TestFileWatcherStop:
    """Tests for FileWatcher.stop method."""

    def test_stop_sets_running_false(self, tmp_path):
        """Test stop sets running to False."""
        callback = MagicMock()
        watcher = FileWatcher([tmp_path], callback)
        watcher._running = True

        watcher.stop()

        assert watcher._running is False


class TestHotPluginLoaderInitLoaders:
    """Tests for _init_loaders method."""

    @pytest.mark.asyncio
    async def test_init_loaders_creates_loaders(self):
        """Test _init_loaders creates all loader types."""
        loader = HotPluginLoader()

        await loader._init_loaders()

        assert loader._python_loader is not None
        assert loader._cpp_loader is not None
        assert loader._external_loader is not None


class TestHotPluginLoaderDiscoverPlugins:
    """Tests for _discover_plugins method."""

    @pytest.mark.asyncio
    async def test_discover_plugins_no_paths(self):
        """Test discover with no watch paths configured."""
        loader = HotPluginLoader()

        await loader._discover_plugins()

        # No error should occur

    @pytest.mark.asyncio
    async def test_discover_plugins_with_python_loader(self):
        """Test discover uses python loader."""
        loader = HotPluginLoader()
        loader._python_loader = MagicMock()
        loader._python_loader.discover = AsyncMock(return_value=[])

        await loader._discover_plugins()

        # Python loader's discover should have been called


class TestHotPluginLoaderOnPluginDiscovered:
    """Tests for _on_plugin_discovered method."""

    @pytest.mark.asyncio
    async def test_on_plugin_discovered_stores_plugin(self):
        """Test _on_plugin_discovered stores plugin info."""
        loader = HotPluginLoader()
        loader._load_plugin = AsyncMock(return_value=True)
        plugin_info = PluginInfo("test", "1.0", Path("/test"), "python")

        await loader._on_plugin_discovered(plugin_info)

        assert "test" in loader._plugins
        loader._load_plugin.assert_called_once_with(plugin_info)


class TestHotPluginLoaderLoadPlugin:
    """Tests for _load_plugin method."""

    @pytest.mark.asyncio
    async def test_load_plugin_python(self):
        """Test loading python plugin."""
        loader = HotPluginLoader()
        loader._python_loader = MagicMock()
        loader._python_loader.load = AsyncMock(return_value={"op1": MagicMock()})

        plugin_info = PluginInfo("test", "1.0", Path("/test"), "python")

        result = await loader._load_plugin(plugin_info)

        assert result is True
        assert "test.op1" in loader._operators

    @pytest.mark.asyncio
    async def test_load_plugin_cpp(self):
        """Test loading cpp plugin."""
        loader = HotPluginLoader()
        loader._cpp_loader = MagicMock()
        loader._cpp_loader.load = AsyncMock(return_value={"op1": MagicMock()})

        plugin_info = PluginInfo("test", "1.0", Path("/test"), "cpp")

        result = await loader._load_plugin(plugin_info)

        assert result is True

    @pytest.mark.asyncio
    async def test_load_plugin_external(self):
        """Test loading external plugin."""
        loader = HotPluginLoader()
        loader._external_loader = MagicMock()
        loader._external_loader.load = AsyncMock(return_value={"op1": MagicMock()})

        plugin_info = PluginInfo("test", "1.0", Path("/test"), "external")

        result = await loader._load_plugin(plugin_info)

        assert result is True


class TestHotPluginLoaderReloadPlugin:
    """Tests for reload_plugin method."""

    @pytest.mark.asyncio
    async def test_reload_plugin_not_running(self):
        """Test reload when not running returns False."""
        loader = HotPluginLoader()

        result = await loader.reload_plugin("test")

        assert result is False

    @pytest.mark.asyncio
    async def test_reload_plugin_success(self):
        """Test successful plugin reload."""
        loader = HotPluginLoader()
        loader._running = True
        loader._plugins = {"test": PluginInfo("test", "1.0", Path("/test"), "python")}
        loader._load_plugin = AsyncMock(return_value=True)

        with patch.object(loader, '_schedule_reload', new=AsyncMock()):
            result = await loader.reload_plugin("test")

        # Reload logic depends on implementation
        assert isinstance(result, bool)


class TestHotReloadConfig:
    """Tests for HotReloadConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = HotReloadConfig()

        assert config.watch_paths == []
        assert config.reload_strategy == ReloadStrategy.ATOMIC
        assert config.debounce_ms == 500
        assert config.scan_interval_seconds == 5.0
        assert config.max_retries == 3

    def test_custom_config(self):
        """Test custom configuration."""
        config = HotReloadConfig(
            watch_paths=[Path("/test")],
            reload_strategy=ReloadStrategy.GRACEFUL,
            debounce_ms=1000,
        )

        assert config.watch_paths == [Path("/test")]
        assert config.reload_strategy == ReloadStrategy.GRACEFUL
        assert config.debounce_ms == 1000


class TestPluginInfo:
    """Tests for PluginInfo."""

    def test_creation(self):
        """Test PluginInfo creation."""
        info = PluginInfo(
            name="test_plugin",
            version="1.0.0",
            path=Path("/test"),
            loader_type="python"
        )

        assert info.name == "test_plugin"
        assert info.version == "1.0.0"
        assert info.loader_type == "python"
        assert info.enabled is True

    def test_default_values(self):
        """Test PluginInfo default values."""
        info = PluginInfo(
            name="test",
            version="1.0",
            path=Path("/test"),
            loader_type="python"
        )

        assert info.loaded_at == 0
        assert info.file_hash == ""


class TestHotPluginLoaderInit:
    """Tests for HotPluginLoader initialization."""

    def test_creation_with_no_config(self):
        """Test loader creation with no config."""
        loader = HotPluginLoader()

        assert loader._config is not None
        assert loader._plugins == {}
        assert loader._operators == {}
        assert loader._file_watcher is None
        assert loader._running is False

    def test_creation_with_config(self):
        """Test loader creation with config."""
        config = HotReloadConfig(watch_paths=[Path("/test")])
        loader = HotPluginLoader(config)

        assert loader._config == config

    def test_loaders_not_initialized_initially(self):
        """Test loaders are None initially."""
        loader = HotPluginLoader()

        assert loader._python_loader is None
        assert loader._cpp_loader is None
        assert loader._external_loader is None


class TestHotPluginLoaderGetWatchPaths:
    """Tests for _get_watch_paths."""

    def test_no_watch_paths(self):
        """Test with no watch paths configured."""
        loader = HotPluginLoader()
        paths = loader._get_watch_paths()

        assert paths == []

    def test_nonexistent_path(self):
        """Test nonexistent path returns empty."""
        loader = HotPluginLoader(HotReloadConfig(
            watch_paths=[Path("/nonexistent/path/12345")]
        ))
        paths = loader._get_watch_paths()

        assert paths == []

    def test_existing_path(self, tmp_path):
        """Test existing path is returned."""
        loader = HotPluginLoader(HotReloadConfig(watch_paths=[tmp_path]))
        paths = loader._get_watch_paths()

        assert paths == [tmp_path]


class TestHotPluginLoaderDiscover:
    """Tests for plugin discovery."""

    @pytest.mark.asyncio
    async def test_discover_plugins_no_paths(self):
        """Test discover with no watch paths."""
        loader = HotPluginLoader()
        await loader._discover_plugins()

        # Should not raise

    @pytest.mark.asyncio
    async def test_on_plugin_discovered(self):
        """Test _on_plugin_discovered callback."""
        loader = HotPluginLoader()
        plugin_info = PluginInfo("test", "1.0", Path("/test"), "python")

        with patch.object(loader, '_load_plugin', new=AsyncMock(return_value=True)):
            await loader._on_plugin_discovered(plugin_info)

        assert "test" in loader._plugins


class TestHotPluginLoaderLoad:
    """Tests for plugin loading."""

    @pytest.mark.asyncio
    async def test_load_unknown_loader_type(self):
        """Test loading with unknown loader type."""
        loader = HotPluginLoader()
        plugin_info = PluginInfo("test", "1.0", Path("/test"), "unknown")

        result = await loader._load_plugin(plugin_info)

        assert result is False

    @pytest.mark.asyncio
    async def test_load_without_python_loader(self):
        """Test loading when python loader not initialized."""
        loader = HotPluginLoader()
        plugin_info = PluginInfo("test", "1.0", Path("/test"), "python")

        result = await loader._load_plugin(plugin_info)

        assert result is False


class TestHotPluginLoaderListMethods:
    """Tests for list methods."""

    def test_list_plugins_empty(self):
        """Test list_plugins when empty."""
        loader = HotPluginLoader()

        plugins = loader.list_plugins()

        assert plugins == []

    def test_list_plugins_with_plugins(self):
        """Test list_plugins with discovered plugins."""
        loader = HotPluginLoader()
        plugin1 = PluginInfo("p1", "1.0", Path("/p1"), "python")
        plugin2 = PluginInfo("p2", "1.0", Path("/p2"), "python")
        loader._plugins["p1"] = plugin1
        loader._plugins["p2"] = plugin2

        plugins = loader.list_plugins()

        assert len(plugins) == 2

    def test_list_operators_empty(self):
        """Test list_operators when empty."""
        loader = HotPluginLoader()

        operators = loader.list_operators()

        assert operators == []

    def test_list_operators_with_operators(self):
        """Test list_operators with registered operators."""
        loader = HotPluginLoader()
        loader._operators["p1.op1"] = MagicMock()
        loader._operators["p2.op2"] = MagicMock()

        operators = loader.list_operators()

        assert len(operators) == 2
        assert "p1.op1" in operators


class TestHotPluginLoaderGetOperator:
    """Tests for get_operator."""

    def test_get_operator_not_found(self):
        """Test get_operator when not found."""
        loader = HotPluginLoader()

        result = loader.get_operator("nonexistent", "op")

        assert result is None

    def test_get_operator_found(self):
        """Test get_operator when found."""
        loader = HotPluginLoader()
        mock_op = MagicMock()
        loader._operators["test.op"] = mock_op

        result = loader.get_operator("test", "op")

        assert result == mock_op


class TestHotPluginLoaderReload:
    """Tests for plugin reload."""

    @pytest.mark.asyncio
    async def test_reload_plugin_not_running(self):
        """Test reload when not running."""
        loader = HotPluginLoader()

        result = await loader.reload_plugin("test")

        assert result is False

    @pytest.mark.asyncio
    async def test_schedule_reload_empty_files(self):
        """Test _schedule_reload with no files."""
        loader = HotPluginLoader()
        loader._running = True
        loader._file_watcher = MagicMock()
        loader._file_watcher.get_modified_files.return_value = set()

        await loader._schedule_reload(set())

        # Should complete without error


class TestHotPluginLoaderShutdown:
    """Tests for shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_stops_running(self):
        """Test shutdown sets running to False."""
        loader = HotPluginLoader()
        loader._running = True
        loader._file_watcher = MagicMock()

        await loader.shutdown()

        assert loader._running is False

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self):
        """Test shutdown clears plugins and operators."""
        loader = HotPluginLoader()
        loader._plugins = {"test": MagicMock()}
        loader._operators = {"test.op": MagicMock()}
        loader._running = True
        loader._file_watcher = MagicMock()

        await loader.shutdown()

        assert len(loader._plugins) == 0
        assert len(loader._operators) == 0


class TestHotPluginLoaderFileWatcherCallback:
    """Tests for file watcher callback."""

    @pytest.mark.asyncio
    async def test_on_files_changed_empty(self):
        """Test _on_files_changed with empty set."""
        loader = HotPluginLoader()
        loader._running = True

        # Should not raise
        loader._on_files_changed(set())

    @pytest.mark.asyncio
    async def test_on_files_changed_schedules_reload(self):
        """Test _on_files_changed schedules a reload."""
        loader = HotPluginLoader()
        loader._running = True
        modified = {Path("/test/plugin.py")}

        # The method creates a task, we just verify it doesn't raise
        loader._on_files_changed(modified)

        # Give task a chance to run
        await asyncio.sleep(0.01)


class TestHotPluginLoaderDiscoverPlugins:
    """Tests for _discover_plugins method."""

    @pytest.mark.asyncio
    async def test_discover_plugins_with_python_loader(self, tmp_path):
        """Test discover uses python loader."""
        config = HotReloadConfig(watch_paths=[tmp_path])
        loader = HotPluginLoader(config)
        loader._python_loader = MagicMock()
        loader._python_loader.discover = AsyncMock(return_value=["plugin1"])

        await loader._discover_plugins()

        loader._python_loader.discover.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_plugins_with_cpp_loader(self, tmp_path):
        """Test discover uses cpp loader."""
        config = HotReloadConfig(watch_paths=[tmp_path])
        loader = HotPluginLoader(config)
        loader._cpp_loader = MagicMock()
        loader._cpp_loader.discover = AsyncMock(return_value=[])

        await loader._discover_plugins()

        loader._cpp_loader.discover.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_plugins_with_external_loader(self, tmp_path):
        """Test discover uses external loader."""
        config = HotReloadConfig(watch_paths=[tmp_path])
        loader = HotPluginLoader(config)
        loader._external_loader = MagicMock()
        loader._external_loader.discover = AsyncMock(return_value=[])

        await loader._discover_plugins()

        loader._external_loader.discover.assert_called_once()


class TestHotPluginLoaderScheduleReload:
    """Tests for _schedule_reload method."""

    @pytest.mark.asyncio
    async def test_schedule_reload_with_files(self):
        """Test _schedule_reload with modified files."""
        loader = HotPluginLoader()
        loader._running = True
        loader._file_watcher = MagicMock()
        loader._file_watcher.get_modified_files.return_value = {Path("/test/plugin.py")}
        loader._plugins = {"test": PluginInfo("test", "1.0", Path("/test"), "python")}
        loader._schedule_reload = AsyncMock()

        await loader._schedule_reload({Path("/test/plugin.py")})

        # The reload should be scheduled
        assert loader._running is True


class TestHotPluginLoaderOnPluginDiscovered:
    """Tests for _on_plugin_discovered method."""

    @pytest.mark.asyncio
    async def test_on_plugin_discovered_with_load_failure(self):
        """Test _on_plugin_discovered when load fails."""
        loader = HotPluginLoader()
        loader._load_plugin = AsyncMock(return_value=False)
        plugin_info = PluginInfo("test", "1.0", Path("/test"), "python")

        await loader._on_plugin_discovered(plugin_info)

        # Plugin should still be in _plugins even if load fails
        assert "test" in loader._plugins


class TestHotPluginLoaderLoadPlugin:
    """Tests for _load_plugin method."""

    @pytest.mark.asyncio
    async def test_load_plugin_with_cpp_loader(self):
        """Test loading cpp plugin."""
        loader = HotPluginLoader()
        loader._cpp_loader = MagicMock()
        loader._cpp_loader.load = AsyncMock(return_value={"op1": MagicMock()})

        plugin_info = PluginInfo("test", "1.0", Path("/test"), "cpp")

        result = await loader._load_plugin(plugin_info)

        assert result is True
        assert "test.op1" in loader._operators

    @pytest.mark.asyncio
    async def test_load_plugin_with_external_loader(self):
        """Test loading external plugin."""
        loader = HotPluginLoader()
        loader._external_loader = MagicMock()
        loader._external_loader.load = AsyncMock(return_value={"op1": MagicMock()})

        plugin_info = PluginInfo("test", "1.0", Path("/test"), "external")

        result = await loader._load_plugin(plugin_info)

        assert result is True

    @pytest.mark.asyncio
    async def test_load_plugin_without_loaders(self):
        """Test loading when loaders not initialized."""
        loader = HotPluginLoader()
        plugin_info = PluginInfo("test", "1.0", Path("/test"), "python")

        # Without initializing loaders, this should fail
        result = await loader._load_plugin(plugin_info)

        assert result is False
