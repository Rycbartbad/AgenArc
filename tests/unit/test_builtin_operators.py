"""Unit tests for operators/builtin.py."""

import pytest
from agenarc.operators.builtin import (
    TriggerOperator,
    Memory_IO_Operator,
    Script_Node_Operator,
    Log_Node_Operator,
    Context_Set_Operator,
    Context_Get_Operator,
    BUILTIN_OPERATORS,
    get_builtin_operator,
)
from agenarc.engine.state import StateManager


def create_context():
    """Create a test execution context."""
    sm = StateManager()
    sm.initialize("test_exec", "test_graph")
    return sm


class TestTriggerOperator:
    """Tests for TriggerOperator."""

    def test_name(self):
        """Test operator name."""
        op = TriggerOperator()
        assert op.name == "builtin.trigger"

    def test_description(self):
        """Test operator description."""
        op = TriggerOperator()
        assert op.description == "Entry point trigger for graph execution"

    def test_version(self):
        """Test operator version."""
        op = TriggerOperator()
        assert op.version == "1.0.0"

    def test_input_ports(self):
        """Test operator has no input ports."""
        op = TriggerOperator()
        assert op.get_input_ports() == []

    def test_output_ports(self):
        """Test operator output ports."""
        op = TriggerOperator()
        ports = op.get_output_ports()
        assert len(ports) == 1
        assert ports[0].name == "payload"

    @pytest.mark.asyncio
    async def test_execute_returns_payload(self):
        """Test execute returns payload from context."""
        op = TriggerOperator()
        ctx = create_context()
        ctx.set("trigger_payload", {"key": "value"})

        result = await op.execute({}, ctx)

        assert result["payload"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_execute_empty_payload(self):
        """Test execute with no payload set."""
        op = TriggerOperator()
        ctx = create_context()

        result = await op.execute({}, ctx)

        assert result["payload"] == {}


class TestMemory_IO_Operator:
    """Tests for Memory_IO_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Memory_IO_Operator()
        assert op.name == "builtin.memory_io"

    def test_input_ports(self):
        """Test operator input ports."""
        op = Memory_IO_Operator()
        ports = op.get_input_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "key" in port_names
        assert "value" in port_names

    def test_output_ports(self):
        """Test operator output ports."""
        op = Memory_IO_Operator()
        ports = op.get_output_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "value" in port_names
        assert "success" in port_names

    @pytest.mark.asyncio
    async def test_write(self):
        """Test memory write operation."""
        op = Memory_IO_Operator()
        ctx = create_context()
        ctx.set("_memory_mode", "write")

        result = await op.execute({"key": "test_key", "value": "test_value"}, ctx)

        assert result["success"] is True
        assert result["value"] == "test_value"

    @pytest.mark.asyncio
    async def test_read(self):
        """Test memory read operation."""
        op = Memory_IO_Operator()
        ctx = create_context()
        ctx.set("_memory_mode", "write")
        await op.execute({"key": "read_key", "value": "read_value"}, ctx)

        ctx.set("_memory_mode", "read")
        result = await op.execute({"key": "read_key"}, ctx)

        assert result["success"] is True
        assert result["value"] == "read_value"

    @pytest.mark.asyncio
    async def test_read_missing_key(self):
        """Test reading non-existent key."""
        op = Memory_IO_Operator()
        ctx = create_context()
        ctx.set("_memory_mode", "read")

        result = await op.execute({"key": "nonexistent"}, ctx)

        assert result["success"] is False
        assert result["value"] is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test memory delete operation."""
        op = Memory_IO_Operator()
        ctx = create_context()
        ctx.set("_memory_mode", "write")
        await op.execute({"key": "delete_key", "value": "to_delete"}, ctx)

        ctx.set("_memory_mode", "delete")
        result = await op.execute({"key": "delete_key"}, ctx)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_missing_key(self):
        """Test operation without key."""
        op = Memory_IO_Operator()
        ctx = create_context()

        result = await op.execute({}, ctx)

        assert result["success"] is False


class TestLog_Node_Operator:
    """Tests for Log_Node_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Log_Node_Operator()
        assert op.name == "builtin.log"

    def test_input_ports(self):
        """Test operator input ports."""
        op = Log_Node_Operator()
        ports = op.get_input_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "message" in port_names
        assert "data" in port_names

    def test_output_ports(self):
        """Test operator output ports."""
        op = Log_Node_Operator()
        ports = op.get_output_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "message" in port_names
        assert "data" in port_names

    @pytest.mark.asyncio
    async def test_execute_passthrough(self):
        """Test log operator passes through inputs."""
        op = Log_Node_Operator()
        ctx = create_context()

        result = await op.execute(
            {"message": "test message", "data": {"key": "value"}},
            ctx
        )

        assert result["message"] == "test message"
        assert result["data"] == {"key": "value"}


class TestContext_Set_Operator:
    """Tests for Context_Set_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Context_Set_Operator()
        assert op.name == "builtin.context_set"

    def test_input_ports(self):
        """Test operator input ports."""
        op = Context_Set_Operator()
        ports = op.get_input_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "key" in port_names
        assert "value" in port_names

    def test_output_ports(self):
        """Test operator output ports."""
        op = Context_Set_Operator()
        ports = op.get_output_ports()
        assert len(ports) == 1
        assert ports[0].name == "success"

    @pytest.mark.asyncio
    async def test_set_value(self):
        """Test setting value in context."""
        op = Context_Set_Operator()
        ctx = create_context()

        result = await op.execute({"key": "test_key", "value": "test_value"}, ctx)

        assert result["success"] is True
        assert ctx.get("test_key") == "test_value"

    @pytest.mark.asyncio
    async def test_set_without_key(self):
        """Test set operation without key."""
        op = Context_Set_Operator()
        ctx = create_context()

        result = await op.execute({"value": "some_value"}, ctx)

        assert result["success"] is False


class TestContext_Get_Operator:
    """Tests for Context_Get_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Context_Get_Operator()
        assert op.name == "builtin.context_get"

    def test_input_ports(self):
        """Test operator input ports."""
        op = Context_Get_Operator()
        ports = op.get_input_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "key" in port_names
        assert "default" in port_names

    def test_output_ports(self):
        """Test operator output ports."""
        op = Context_Get_Operator()
        ports = op.get_output_ports()
        assert len(ports) == 1
        assert ports[0].name == "value"

    @pytest.mark.asyncio
    async def test_get_value(self):
        """Test getting value from context."""
        op = Context_Get_Operator()
        ctx = create_context()
        ctx.set("get_key", "get_value")

        result = await op.execute({"key": "get_key"}, ctx)

        assert result["value"] == "get_value"

    @pytest.mark.asyncio
    async def test_get_with_default(self):
        """Test getting with default value."""
        op = Context_Get_Operator()
        ctx = create_context()

        result = await op.execute({"key": "nonexistent", "default": "default_val"}, ctx)

        assert result["value"] == "default_val"

    @pytest.mark.asyncio
    async def test_get_without_key(self):
        """Test get without key returns None."""
        op = Context_Get_Operator()
        ctx = create_context()

        result = await op.execute({}, ctx)

        assert result["value"] is None


class TestBuiltinOperatorsRegistry:
    """Tests for built-in operators registry."""

    def test_registry_contains_expected_operators(self):
        """Test registry contains expected operators."""
        expected = ["Trigger", "Memory_I/O", "Script_Node", "Log", "Context_Set", "Context_Get"]
        for op_type in expected:
            assert op_type in BUILTIN_OPERATORS

    def test_get_builtin_operator(self):
        """Test getting built-in operator."""
        op = get_builtin_operator("Trigger")
        assert op is not None
        assert isinstance(op, TriggerOperator)

    def test_get_builtin_operator_unknown(self):
        """Test getting unknown operator returns None."""
        op = get_builtin_operator("UnknownType")
        assert op is None


class TestScript_Node_Operator:
    """Tests for Script_Node_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Script_Node_Operator()
        assert op.name == "builtin.script_node"

    def test_input_ports(self):
        """Test operator input ports."""
        op = Script_Node_Operator()
        ports = op.get_input_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "script" in port_names
        assert "timeout" in port_names

    @pytest.mark.asyncio
    async def test_execute_empty_script(self):
        """Test executing empty script."""
        op = Script_Node_Operator()
        ctx = create_context()

        result = await op.execute({}, ctx)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_simple_script(self):
        """Test executing simple script."""
        op = Script_Node_Operator()
        ctx = create_context()

        result = await op.execute({"script": "x = 42"}, ctx)

        assert result["success"] is True
