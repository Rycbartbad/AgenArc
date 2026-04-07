"""Unit tests for plugins/manager.py."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from agenarc.plugins.manager import PluginManager
from agenarc.plugins.hot_loader import PluginInfo, HotPluginLoader, ReloadStrategy
from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port


class MockOperator(IOperator):
    """Mock operator for testing."""

    @property
    def name(self) -> str:
        return "mock.test_operator"

    @property
    def description(self) -> str:
        return "A mock operator for testing"

    def get_input_ports(self) -> list[Port]:
        return [Port(name="input", type="string")]

    def get_output_ports(self) -> list[Port]:
        return [Port(name="output", type="string")]

    async def execute(self, inputs, context):
        return {"output": inputs.get("input", "")}


class TestPluginManagerInit:
    """Tests for PluginManager initialization."""

    def test_init_with_no_dirs(self):
        """Test initialization with default values."""
        manager = PluginManager()

        assert manager._plugin_dirs == []
        assert manager._bundle_paths == []
        assert manager._operators == {}
        assert manager._plugins == {}
        assert manager._hot_loader is None
        assert manager.is_initialized is False

    def test_init_with_plugin_dirs(self):
        """Test initialization with custom plugin directories."""
        manager = PluginManager(plugin_dirs=["~/.agenarc/plugins"])

        assert manager._plugin_dirs == ["~/.agenarc/plugins"]

    def test_init_with_bundle_paths(self):
        """Test initialization with bundle paths."""
        bundle_path = Path("/test/bundle")
        manager = PluginManager(bundle_paths=[bundle_path])

        assert manager._bundle_paths == [bundle_path]


class TestPluginManagerInitialize:
    """Tests for PluginManager.initialize()."""

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self):
        """Test initialize does nothing if already initialized."""
        manager = PluginManager()
        manager._initialized = True

        await manager.initialize()

        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_creates_hot_loader(self):
        """Test initialize creates HotPluginLoader."""
        with patch.object(HotPluginLoader, 'initialize', new=AsyncMock()):
            manager = PluginManager()
            await manager.initialize()

            assert manager._hot_loader is not None
            assert manager.is_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_with_multiple_plugin_dirs(self):
        """Test initialize configures hot loader with multiple paths."""
        with patch.object(HotPluginLoader, 'initialize', new=AsyncMock()):
            manager = PluginManager(plugin_dirs=["~/.agenarc/plugins", "/usr/local/agenarc/plugins"])
            await manager.initialize()

            config = manager._hot_loader._config
            assert len(config.watch_paths) == 2


class TestPluginManagerDiscoverBundlePlugins:
    """Tests for _discover_bundle_plugins."""

    @pytest.mark.asyncio
    async def test_discover_bundle_plugins_empty(self):
        """Test discover with no bundle paths."""
        manager = PluginManager()

        await manager._discover_bundle_plugins()

        # No error should occur

    @pytest.mark.asyncio
    async def test_discover_bundle_plugins_no_plugins_dir(self):
        """Test discover when bundle has no plugins directory."""
        with patch.object(HotPluginLoader, 'initialize', new=AsyncMock()):
            manager = PluginManager()
            await manager.initialize()

            bundle_path = Path("/test/bundle")
            await manager._discover_bundle_plugins()

            # Should not error when plugins dir doesn't exist

    @pytest.mark.asyncio
    async def test_discover_bundle_plugins_with_valid_plugin(self, tmp_path):
        """Test discover finds embedded plugin."""
        # Create bundle structure
        bundle = tmp_path / "test_agent.agrc"
        bundle.mkdir()
        plugins_dir = bundle / "plugins"
        plugins_dir.mkdir()

        plugin_dir = plugins_dir / "embedded_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "agenarc.json").write_text('{"name": "embedded_plugin"}')

        with patch.object(HotPluginLoader, 'initialize', new=AsyncMock()):
            manager = PluginManager(bundle_paths=[bundle])
            await manager.initialize()
            await manager._discover_bundle_plugins()


class TestPluginManagerRegisterOperator:
    """Tests for register_operator()."""

    def test_register_operator_with_function_name(self):
        """Test registering operator with full key."""
        manager = PluginManager()
        mock_op = MagicMock()

        manager.register_operator("my_plugin", "my_operator", mock_op)

        assert manager._operators["my_plugin.my_operator"] == mock_op

    def test_register_operator_without_function_name(self):
        """Test registering operator with just plugin name."""
        manager = PluginManager()
        mock_op = MagicMock()

        manager.register_operator("my_plugin", "", mock_op)

        assert manager._operators["my_plugin"] == mock_op


class TestPluginManagerGetOperator:
    """Tests for get_operator()."""

    def test_get_operator_from_local_cache(self):
        """Test get_operator returns cached operator."""
        manager = PluginManager()
        mock_op = MagicMock()
        manager._operators["test.op"] = mock_op

        result = manager.get_operator("test", "op")

        assert result == mock_op

    def test_get_operator_with_single_name(self):
        """Test get_operator with just plugin name."""
        manager = PluginManager()
        mock_op = MagicMock()
        manager._operators["my_plugin"] = mock_op

        result = manager.get_operator("my_plugin")

        assert result == mock_op

    def test_get_operator_not_found(self):
        """Test get_operator returns None when not found."""
        manager = PluginManager()

        result = manager.get_operator("unknown", "plugin")

        assert result is None

    def test_get_operator_from_hot_loader(self):
        """Test get_operator falls back to hot loader."""
        manager = PluginManager()
        mock_op = MagicMock()
        mock_loader = MagicMock()
        mock_loader.get_operator.return_value = mock_op
        manager._hot_loader = mock_loader

        result = manager.get_operator("test", "op")

        assert result == mock_op
        assert manager._operators["test.op"] == mock_op


class TestPluginManagerListOperators:
    """Tests for list_operators()."""

    def test_list_operators_empty(self):
        """Test list_operators when empty."""
        manager = PluginManager()

        result = manager.list_operators()

        assert result == []

    def test_list_operators_returns_all(self):
        """Test list_operators returns all registered operators."""
        manager = PluginManager()
        manager._operators["op1"] = MagicMock()
        manager._operators["op2"] = MagicMock()

        result = manager.list_operators()

        assert set(result) == {"op1", "op2"}


class TestPluginManagerListPlugins:
    """Tests for list_plugins()."""

    def test_list_plugins_empty(self):
        """Test list_plugins when empty."""
        manager = PluginManager()

        result = manager.list_plugins()

        assert result == []

    def test_list_plugins_returns_all(self):
        """Test list_plugins returns all discovered plugins."""
        manager = PluginManager()
        plugin1 = PluginInfo("plugin1", "1.0.0", Path("/p1"), "python")
        plugin2 = PluginInfo("plugin2", "1.0.0", Path("/p2"), "python")
        manager._plugins["plugin1"] = plugin1
        manager._plugins["plugin2"] = plugin2

        result = manager.list_plugins()

        assert len(result) == 2


class TestPluginManagerReloadPlugin:
    """Tests for reload_plugin()."""

    @pytest.mark.asyncio
    async def test_reload_without_hot_loader(self):
        """Test reload returns False when no hot loader."""
        manager = PluginManager()

        result = await manager.reload_plugin("test_plugin")

        assert result is False

    @pytest.mark.asyncio
    async def test_reload_plugin_success(self):
        """Test successful plugin reload."""
        manager = PluginManager()
        mock_loader = MagicMock()
        mock_loader.reload_plugin = AsyncMock(return_value=True)
        mock_loader.list_operators.return_value = ["test.op"]
        mock_loader.get_operator.return_value = MagicMock()
        manager._hot_loader = mock_loader
        manager._operators["test.op"] = MagicMock()

        result = await manager.reload_plugin("test")

        assert result is True

    @pytest.mark.asyncio
    async def test_reload_plugin_failure(self):
        """Test failed plugin reload."""
        manager = PluginManager()
        mock_loader = MagicMock()
        mock_loader.reload_plugin = AsyncMock(return_value=False)
        manager._hot_loader = mock_loader

        result = await manager.reload_plugin("test")

        assert result is False


class TestPluginManagerShutdown:
    """Tests for shutdown()."""

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self):
        """Test shutdown clears all state."""
        manager = PluginManager()
        manager._operators = {"test": MagicMock()}
        manager._plugins = {"test": MagicMock()}
        mock_loader = MagicMock()
        mock_loader.shutdown = AsyncMock()
        manager._hot_loader = mock_loader

        await manager.shutdown()

        assert len(manager._operators) == 0
        assert len(manager._plugins) == 0
        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_without_hot_loader(self):
        """Test shutdown works without hot loader."""
        manager = PluginManager()

        await manager.shutdown()

        # Should not error
        assert manager._initialized is False


class TestPluginManagerHotLoader:
    """Tests for hot_loader property."""

    def test_hot_loader_property(self):
        """Test hot_loader returns the hot loader."""
        manager = PluginManager()
        mock_loader = MagicMock()
        manager._hot_loader = mock_loader

        assert manager.hot_loader == mock_loader

    def test_hot_loader_property_none(self):
        """Test hot_loader returns None when not set."""
        manager = PluginManager()

        assert manager.hot_loader is None
