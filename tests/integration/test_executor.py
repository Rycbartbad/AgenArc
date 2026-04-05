"""Integration tests for engine/executor.py."""

import pytest
from agenarc.engine.executor import ExecutionEngine, ExecutionMode, NodeStatus
from agenarc.engine.state import StateManager
from agenarc.operators.builtin import BUILTIN_OPERATORS
from agenarc.plugins.manager import PluginManager
from agenarc.protocol.schema import NodeType, Edge, Graph, Node


def create_test_engine():
    """Create a test execution engine with all built-in operators."""
    plugin_manager = PluginManager()
    engine = ExecutionEngine(plugin_manager=plugin_manager)

    for node_type, operator_class in BUILTIN_OPERATORS.items():
        if operator_class is not None:
            engine.register_builtin_operator(node_type, operator_class)

    return engine


class TestExecutionEngine:
    """Integration tests for ExecutionEngine."""

    def test_engine_creation(self):
        """Test engine creation."""
        engine = create_test_engine()
        assert engine.plugin_manager is not None
        assert engine.max_parallel == 4
        assert engine.enable_checkpoint is True

    def test_register_builtin_operator(self):
        """Test registering built-in operators."""
        engine = create_test_engine()
        assert len(engine._builtin_operators) > 0

    def test_load_simple_protocol(self):
        """Test loading a simple protocol."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                }
            ],
            "edges": []
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        assert engine.graph is not None
        assert engine.graph.entryPoint == "trigger_1"

    def test_load_invalid_protocol(self):
        """Test loading invalid protocol."""
        data = {
            "version": "1.0.0",
            "entryPoint": "nonexistent",
            "nodes": [
                {"id": "a", "type": "Trigger", "label": "A"}
            ],
            "edges": []
        }
        engine = create_test_engine()

        with pytest.raises(ValueError, match="Graph validation errors"):
            engine.load_protocol(data, validate=False)

    @pytest.mark.asyncio
    async def test_execute_empty_graph(self):
        """Test executing empty graph."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"}
            ],
            "edges": []
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute()

        assert result.status == "success"
        assert result.execution_id != ""

    @pytest.mark.asyncio
    async def test_execute_single_node(self):
        """Test executing single node."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start",
                    "outputs": [{"name": "payload", "type": "any"}]
                }
            ],
            "edges": []
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute()

        assert result.status == "success"
        assert "trigger_1" in result.node_results
        assert result.node_results["trigger_1"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_linear_flow(self):
        """Test executing linear flow of nodes."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start",
                    "outputs": [{"name": "payload", "type": "any"}]
                },
                {
                    "id": "log_1",
                    "type": "Log",
                    "label": "Log",
                    "inputs": [
                        {"name": "message", "type": "string"},
                        {"name": "data", "type": "any"}
                    ],
                    "outputs": [
                        {"name": "message", "type": "string"},
                        {"name": "data", "type": "any"}
                    ]
                }
            ],
            "edges": [
                {
                    "source": "trigger_1",
                    "sourcePort": "payload",
                    "target": "log_1",
                    "targetPort": "message"
                }
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute({"trigger_payload": "test message"})

        assert result.status == "success"
        assert result.node_results["trigger_1"].status == NodeStatus.COMPLETED
        assert result.node_results["log_1"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_with_context(self):
        """Test executing with context values."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                },
                {
                    "id": "context_set",
                    "type": "Context_Set",
                    "label": "Set Context"
                },
                {
                    "id": "context_get",
                    "type": "Context_Get",
                    "label": "Get Context"
                }
            ],
            "edges": [
                {"source": "trigger_1", "target": "context_set"},
                {"source": "context_set", "target": "context_get"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute()

        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_execute_sync_mode(self):
        """Test executing in sync mode."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"}
            ],
            "edges": []
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute(mode=ExecutionMode.SYNC)

        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_execute_no_graph_raises_error(self):
        """Test executing without loading graph raises error."""
        engine = create_test_engine()

        with pytest.raises(RuntimeError, match="No graph loaded"):
            await engine.execute()

    def test_stop_execution(self):
        """Test stopping execution."""
        engine = create_test_engine()
        assert engine.is_running is False

    def test_get_operator_for_node(self):
        """Test getting operator for node type."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"}
            ],
            "edges": []
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        node = engine.graph.get_node("trigger_1")
        operator = engine.get_operator(node)

        assert operator is not None
        assert operator.name == "builtin.trigger"


class TestGraphResult:
    """Tests for GraphResult."""

    @pytest.mark.asyncio
    async def test_graph_result_structure(self):
        """Test GraphResult has correct structure."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"}
            ],
            "edges": []
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute()

        assert hasattr(result, "execution_id")
        assert hasattr(result, "status")
        assert hasattr(result, "node_results")
        assert hasattr(result, "final_outputs")
        assert hasattr(result, "duration_ms")


class TestNodeExecutionTracking:
    """Tests for node execution tracking."""

    @pytest.mark.asyncio
    async def test_node_status_tracking(self):
        """Test node status is tracked correctly."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"}
            ],
            "edges": []
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        await engine.execute()

        assert engine._node_statuses["trigger_1"] == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_node_outputs_stored(self):
        """Test node outputs are stored."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start",
                    "outputs": [{"name": "payload", "type": "any"}]
                }
            ],
            "edges": []
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        await engine.execute({"trigger_payload": "test"})

        assert "trigger_1" in engine._node_outputs
        assert engine._node_outputs["trigger_1"]["payload"] == "test"
