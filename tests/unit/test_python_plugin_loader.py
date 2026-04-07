"""Unit tests for plugins/loaders/python.py."""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from agenarc.plugins.loaders.python import PythonPluginLoader
from agenarc.plugins.hot_loader import PluginInfo


class TestPythonPluginLoaderDiscover:
    """Tests for PythonPluginLoader.discover()."""

    @pytest.mark.asyncio
    async def test_discover_empty_directory(self, tmp_path):
        """Test discover on empty directory."""
        loader = PythonPluginLoader()
        callback = MagicMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_nonexistent_directory(self, tmp_path):
        """Test discover on nonexistent directory."""
        loader = PythonPluginLoader()
        callback = MagicMock()

        result = await loader.discover(tmp_path / "nonexistent", callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_with_valid_plugin(self, tmp_path):
        """Test discover finds valid plugin."""
        # Create plugin structure
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('{"name": "test_plugin", "version": "1.0.0"}')

        loader = PythonPluginLoader()
        callback = AsyncMock()

        result = await loader.discover(tmp_path, callback)

        assert result == ["test_plugin"]
        callback.assert_called_once()
        call_arg = callback.call_args[0][0]
        assert call_arg.name == "test_plugin"
        assert call_arg.version == "1.0.0"
        assert call_arg.loader_type == "python"

    @pytest.mark.asyncio
    async def test_discover_with_multiple_plugins(self, tmp_path):
        """Test discover finds multiple plugins."""
        plugin1 = tmp_path / "plugin1"
        plugin1.mkdir()
        (plugin1 / "agenarc.json").write_text('{"name": "plugin1"}')

        plugin2 = tmp_path / "plugin2"
        plugin2.mkdir()
        (plugin2 / "agenarc.json").write_text('{"name": "plugin2"}')

        loader = PythonPluginLoader()
        callback = AsyncMock()

        result = await loader.discover(tmp_path, callback)

        assert len(result) == 2
        assert set(result) == {"plugin1", "plugin2"}

    @pytest.mark.asyncio
    async def test_discover_skips_directories_without_manifest(self, tmp_path):
        """Test discover skips directories without agenarc.json."""
        plugin_dir = tmp_path / "invalid_plugin"
        plugin_dir.mkdir()
        # No manifest file

        loader = PythonPluginLoader()
        callback = AsyncMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_skips_files(self, tmp_path):
        """Test discover skips files."""
        (tmp_path / "not_a_plugin.txt").write_text("content")

        loader = PythonPluginLoader()
        callback = AsyncMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_with_invalid_json(self, tmp_path):
        """Test discover handles invalid JSON gracefully."""
        plugin_dir = tmp_path / "bad_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "agenarc.json").write_text("not valid json {{{")

        loader = PythonPluginLoader()
        callback = AsyncMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_uses_folder_name_if_name_missing(self, tmp_path):
        """Test discover uses folder name if manifest has no name."""
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "agenarc.json").write_text('{"version": "2.0.0"}')

        loader = PythonPluginLoader()
        callback = AsyncMock()

        result = await loader.discover(tmp_path, callback)

        assert result == ["my_plugin"]
        call_arg = callback.call_args[0][0]
        assert call_arg.name == "my_plugin"


class TestPythonPluginLoaderLoad:
    """Tests for PythonPluginLoader.load()."""

    @pytest.mark.asyncio
    async def test_load_missing_entry_file(self, tmp_path):
        """Test load fails gracefully when entry file missing."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('{"name": "test_plugin", "entry": "nonexistent.py"}')

        plugin_info = PluginInfo(
            name="test_plugin",
            version="1.0.0",
            path=manifest,
            loader_type="python"
        )

        loader = PythonPluginLoader()
        result = await loader.load(plugin_info)

        assert result == {}

    @pytest.mark.asyncio
    async def test_load_with_valid_operator(self, tmp_path):
        """Test load successfully loads an operator."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('{"name": "test_plugin", "operators": ["TestOperator"]}')

        plugin_py = plugin_dir / "plugin.py"
        plugin_py.write_text('''
from agenarc.operators.operator import IOperator

class TestOperator(IOperator):
    @property
    def name(self):
        return "test_plugin.test_operator"

    def get_input_ports(self):
        return []

    def get_output_ports(self):
        return []

    async def execute(self, inputs, context):
        return {"result": "success"}
''')

        plugin_info = PluginInfo(
            name="test_plugin",
            version="1.0.0",
            path=manifest,
            loader_type="python"
        )

        loader = PythonPluginLoader()
        result = await loader.load(plugin_info)

        assert "TestOperator" in result
        assert result["TestOperator"].name == "test_plugin.test_operator"

    @pytest.mark.asyncio
    async def test_load_auto_discovers_iooperator_subclasses(self, tmp_path):
        """Test load auto-discovers IOperator subclasses."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('{"name": "test_plugin"}')  # No operators listed

        plugin_py = plugin_dir / "plugin.py"
        plugin_py.write_text('''
from agenarc.operators.operator import IOperator

class AutoDiscoveredOperator(IOperator):
    @property
    def name(self):
        return "test.auto_discovered"

    def get_input_ports(self):
        return []

    def get_output_ports(self):
        return []

    async def execute(self, inputs, context):
        return {}
''')

        plugin_info = PluginInfo(
            name="test_plugin",
            version="1.0.0",
            path=manifest,
            loader_type="python"
        )

        loader = PythonPluginLoader()
        result = await loader.load(plugin_info)

        assert "AutoDiscoveredOperator" in result

    @pytest.mark.asyncio
    async def test_load_caches_module(self, tmp_path):
        """Test load caches the module."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('{"name": "test_plugin", "operators": ["TestOperator"]}')

        plugin_py = plugin_dir / "plugin.py"
        plugin_py.write_text('''
from agenarc.operators.operator import IOperator

class TestOperator(IOperator):
    @property
    def name(self):
        return "test.test"

    def get_input_ports(self):
        return []

    def get_output_ports(self):
        return []

    async def execute(self, inputs, context):
        return {}
''')

        plugin_info = PluginInfo(
            name="test_plugin",
            version="1.0.0",
            path=manifest,
            loader_type="python"
        )

        loader = PythonPluginLoader()
        await loader.load(plugin_info)

        # Module should be cached
        assert "test_plugin" in loader._plugins

    @pytest.mark.asyncio
    async def test_load_with_default_entry(self, tmp_path):
        """Test load uses default entry 'plugin.py'."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('{"name": "test_plugin"}')  # No entry specified

        plugin_py = plugin_dir / "plugin.py"
        plugin_py.write_text('''
from agenarc.operators.operator import IOperator

class TestOp(IOperator):
    @property
    def name(self):
        return "test.op"

    def get_input_ports(self):
        return []

    def get_output_ports(self):
        return []

    async def execute(self, inputs, context):
        return {}
''')

        plugin_info = PluginInfo(
            name="test_plugin",
            version="1.0.0",
            path=manifest,
            loader_type="python"
        )

        loader = PythonPluginLoader()
        result = await loader.load(plugin_info)

        assert "TestOp" in result


class TestPythonPluginLoaderUnload:
    """Tests for PythonPluginLoader.unload()."""

    @pytest.mark.asyncio
    async def test_unload_existing_plugin(self, tmp_path):
        """Test unload removes plugin from cache and sys.modules."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('{"name": "test_plugin", "operators": ["TestOperator"]}')

        plugin_py = plugin_dir / "plugin.py"
        plugin_py.write_text('''
from agenarc.operators.operator import IOperator

class TestOperator(IOperator):
    @property
    def name(self):
        return "test.test"

    def get_input_ports(self):
        return []

    def get_output_ports(self):
        return []

    async def execute(self, inputs, context):
        return {}
''')

        plugin_info = PluginInfo(
            name="test_plugin",
            version="1.0.0",
            path=manifest,
            loader_type="python"
        )

        loader = PythonPluginLoader()
        await loader.load(plugin_info)
        assert "test_plugin" in loader._plugins

        result = loader.unload("test_plugin")

        assert result is True
        assert "test_plugin" not in loader._plugins

    @pytest.mark.asyncio
    async def test_unload_nonexistent_plugin(self, tmp_path):
        """Test unload returns False for nonexistent plugin."""
        loader = PythonPluginLoader()

        result = loader.unload("nonexistent_plugin")

        assert result is False


class TestPythonPluginLoaderGetPlugin:
    """Tests for PythonPluginLoader.get_plugin()."""

    @pytest.mark.asyncio
    async def test_get_existing_plugin(self, tmp_path):
        """Test get_plugin returns cached plugin."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('{"name": "test_plugin", "operators": ["TestOperator"]}')

        plugin_py = plugin_dir / "plugin.py"
        plugin_py.write_text('''
from agenarc.operators.operator import IOperator

class TestOperator(IOperator):
    @property
    def name(self):
        return "test.test"

    def get_input_ports(self):
        return []

    def get_output_ports(self):
        return []

    async def execute(self, inputs, context):
        return {}
''')

        plugin_info = PluginInfo(
            name="test_plugin",
            version="1.0.0",
            path=manifest,
            loader_type="python"
        )

        loader = PythonPluginLoader()
        await loader.load(plugin_info)

        module = loader.get_plugin("test_plugin")

        assert module is not None
        assert module.__name__ == "test_plugin"

    @pytest.mark.asyncio
    async def test_get_nonexistent_plugin(self, tmp_path):
        """Test get_plugin returns None for unknown plugin."""
        loader = PythonPluginLoader()

        result = loader.get_plugin("unknown")

        assert result is None
