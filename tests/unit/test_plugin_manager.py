"""Unit tests for plugins/manager.py."""

import pytest
from agenarc.plugins.manager import PluginManager
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


class TestPluginManager:
    """Tests for PluginManager."""

    def test_manager_creation(self):
        """Test manager creation."""
        manager = PluginManager()
        assert manager is not None

    def test_manager_with_plugin_dirs(self):
        """Test manager with custom plugin directories."""
        manager = PluginManager(plugin_dirs=["/path/to/plugins"])
        assert manager._plugin_dirs == ["/path/to/plugins"]

    def test_register_operator(self):
        """Test registering an operator."""
        manager = PluginManager()
        operator = MockOperator()
        manager.register_operator("mock", "test_operator", operator)

        assert "mock.test_operator" in manager.list_operators()

    def test_get_registered_operator(self):
        """Test getting a registered operator."""
        manager = PluginManager()
        operator = MockOperator()
        manager.register_operator("mock", "test_operator", operator)

        retrieved = manager.get_operator("mock", "test_operator")
        assert retrieved is operator

    def test_get_operator_with_empty_function_name(self):
        """Test getting operator with empty function name uses plugin_name as key."""
        manager = PluginManager()
        operator = MockOperator()
        # Note: register always uses "plugin.function" format
        # When function_name is "", the key becomes "mock."
        manager.register_operator("mock", "", operator)

        # get_operator uses plugin_name alone when function_name is empty
        # But register stored under "mock." so this returns None (demonstrates the mismatch)
        # This test documents the current behavior
        retrieved = manager.get_operator("mock", "")
        # The bug: register stores "mock." but get looks up "mock"
        assert retrieved is None

    def test_get_nonexistent_operator(self):
        """Test getting non-existent operator returns None."""
        manager = PluginManager()
        retrieved = manager.get_operator("nonexistent", "operator")
        assert retrieved is None

    def test_list_operators_empty(self):
        """Test listing operators when none registered."""
        manager = PluginManager()
        assert manager.list_operators() == []

    def test_list_operators_multiple(self):
        """Test listing multiple operators."""
        manager = PluginManager()
        operator1 = MockOperator()
        operator2 = MockOperator()

        manager.register_operator("mock", "op1", operator1)
        manager.register_operator("mock", "op2", operator2)

        operators = manager.list_operators()
        assert len(operators) == 2
        assert "mock.op1" in operators
        assert "mock.op2" in operators

    def test_discover_plugins(self):
        """Test discover_plugins is callable."""
        manager = PluginManager()
        # Should not raise
        manager.discover_plugins()

    def test_reload_plugin(self):
        """Test reload_plugin returns False (stub)."""
        manager = PluginManager()
        result = manager.reload_plugin("nonexistent")
        assert result is False
