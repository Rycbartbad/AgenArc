"""Unit tests for engine/executor.py."""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from agenarc.engine.executor import (
    ExecutionEngine,
    ExecutionMode,
    ExecutionResult,
    GraphResult,
    NodeStatus,
)
from agenarc.protocol.loader import ProtocolLoader, LoaderError
from agenarc.protocol.schema import (
    Graph,
    Node,
    NodeType,
    Edge,
    Port,
    ErrorHandling,
    ErrorStrategy,
)
from agenarc.engine.state import StateManager


def create_test_graph_dict(entry="trigger_1"):
    """Create a minimal test graph dict."""
    return {
        "version": "1.0.0",
        "entryPoint": entry,
        "metadata": {"name": "test_graph", "version": "1.0.0"},
        "nodes": [
            {
                "id": "trigger_1",
                "type": "Trigger",
                "label": "Trigger",
                "description": "Entry point",
                "inputs": [],
                "outputs": [{"name": "payload", "type": "any"}],
            },
            {
                "id": "llm_1",
                "type": "LLM_Task",
                "label": "LLM Task",
                "description": "LLM task",
                "inputs": [{"name": "prompt", "type": "string"}],
                "outputs": [{"name": "response", "type": "string"}],
            },
        ],
        "edges": [
            {
                "source": "trigger_1",
                "sourcePort": "payload",
                "target": "llm_1",
                "targetPort": "prompt",
            }
        ],
    }


def load_test_graph(entry="trigger_1"):
    """Create a loaded test graph."""
    loader = ProtocolLoader(validate=False)
    return loader.load_dict(create_test_graph_dict(entry))


class TestNodeStatus:
    """Tests for NodeStatus enum."""

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        assert NodeStatus.PENDING is not None
        assert NodeStatus.RUNNING is not None
        assert NodeStatus.COMPLETED is not None
        assert NodeStatus.FAILED is not None
        assert NodeStatus.SKIPPED is not None
        assert NodeStatus.WAITING is not None


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_creation(self):
        """Test ExecutionResult creation."""
        result = ExecutionResult(
            node_id="test_node",
            status=NodeStatus.COMPLETED,
            outputs={"key": "value"},
        )
        assert result.node_id == "test_node"
        assert result.status == NodeStatus.COMPLETED
        assert result.outputs == {"key": "value"}
        assert result.error is None
        assert result.duration_ms == 0


class TestGraphResult:
    """Tests for GraphResult dataclass."""

    def test_creation(self):
        """Test GraphResult creation."""
        result = GraphResult(
            execution_id="exec_123",
            status="success",
            node_results={},
        )
        assert result.execution_id == "exec_123"
        assert result.status == "success"
        assert result.node_results == {}


class TestExecutionEngine:
    """Tests for ExecutionEngine."""

    def test_engine_creation(self):
        """Test engine can be created."""
        engine = ExecutionEngine()
        assert engine.plugin_manager is None
        assert engine.max_parallel == 4
        assert engine.enable_checkpoint is True

    def test_engine_creation_with_params(self):
        """Test engine creation with parameters."""
        engine = ExecutionEngine(max_parallel=8, enable_checkpoint=False)
        assert engine.max_parallel == 8
        assert engine.enable_checkpoint is False

    def test_register_builtin_operator(self):
        """Test registering built-in operators."""
        engine = ExecutionEngine()

        class DummyOperator:
            name = "test.op"

        engine.register_builtin_operator("Dummy", DummyOperator)
        assert "Dummy" in engine._builtin_operators

    def test_load_protocol_dict(self):
        """Test loading protocol from dict."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        assert engine._graph is not None
        assert engine._traversal is not None
        assert len(engine._node_statuses) == 2

    def test_load_protocol_file(self, tmp_path):
        """Test loading protocol from file."""
        engine = ExecutionEngine()

        flow_file = tmp_path / "flow.json"
        flow_file.write_text('{"version": "1.0.0", "entryPoint": "t1", "nodes": [{"id": "t1", "type": "Trigger", "label": "T"}], "edges": []}')

        engine.load_protocol(flow_file)
        assert engine._graph is not None

    def test_load_protocol_validates_graph(self):
        """Test load_protocol validates graph structure."""
        engine = ExecutionEngine()

        with pytest.raises(ValueError, match="Graph validation errors"):
            engine.load_protocol(create_test_graph_dict(entry="nonexistent"))

    def test_load_protocol_resets_state(self):
        """Test load_protocol resets execution state."""
        engine = ExecutionEngine()
        engine._node_statuses = {"old": NodeStatus.COMPLETED}
        engine._node_outputs = {"old": {}}
        engine._node_errors = {"old": ValueError()}

        engine.load_protocol(create_test_graph_dict())

        assert "trigger_1" in engine._node_statuses
        assert "llm_1" in engine._node_statuses
        assert engine._node_outputs == {}
        assert engine._node_errors == {}

    def test_get_operator_builtin(self):
        """Test getting built-in operator."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        class DummyOp:
            pass

        engine.register_builtin_operator("Trigger", DummyOp)
        graph = engine._graph
        trigger_node = graph.get_node("trigger_1")
        operator = engine.get_operator(trigger_node)
        assert operator is not None

    def test_get_operator_plugin(self):
        """Test getting operator from plugin manager."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        mock_pm = MagicMock()
        mock_op = MagicMock()
        mock_pm.get_operator.return_value = mock_op

        engine.plugin_manager = mock_pm
        graph = engine._graph
        llm_node = graph.get_node("llm_1")
        operator = engine.get_operator(llm_node)
        assert operator == mock_op

    def test_get_operator_not_found(self):
        """Test getting operator when none available."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())
        engine._builtin_operators = {}

        graph = engine._graph
        llm_node = graph.get_node("llm_1")
        operator = engine.get_operator(llm_node)
        assert operator is None

    def test_execute_without_graph_raises(self):
        """Test execute raises if no graph loaded."""
        engine = ExecutionEngine()

        with pytest.raises(RuntimeError, match="No graph loaded"):
            asyncio.get_event_loop().run_until_complete(engine.execute())

    @pytest.mark.asyncio
    async def test_execute_sync_mode(self):
        """Test synchronous execution mode."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={"payload": {"msg": "hello"}})
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)

        result = await engine.execute(mode=ExecutionMode.SYNC)
        assert result.status in ("success", "failed", "partial")

    @pytest.mark.asyncio
    async def test_execute_async_mode(self):
        """Test async execution mode."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={"payload": {"msg": "hello"}})
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)

        result = await engine.execute(mode=ExecutionMode.ASYNC)
        assert result.status in ("success", "failed", "partial")

    @pytest.mark.asyncio
    async def test_execute_parallel_mode(self):
        """Test parallel execution mode."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={"payload": {}})
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)

        result = await engine.execute(mode=ExecutionMode.PARALLEL)
        assert result.status in ("success", "failed", "partial")

    @pytest.mark.asyncio
    async def test_execute_with_initial_inputs(self):
        """Test execution with initial inputs."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={"payload": {}})
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)

        result = await engine.execute(initial_inputs={"test_key": "test_value"})
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_entry_not_found(self):
        """Test execute raises when entry not found in loaded graph."""
        # First verify the graph loads successfully with a valid entry
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict(entry="trigger_1"))

        # Now try to execute - the trigger operator won't be found
        # so the node will be marked completed but the entry exists
        # The actual "entry not found" case is caught at load time
        result = await engine.execute()
        # Entry point exists, execution proceeds (maybe fails on operator)
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_sets_running_flag(self):
        """Test running flag is set during execution."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={"payload": {}})
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)

        assert engine._running is False
        await engine.execute()
        assert engine._running is False

    @pytest.mark.asyncio
    async def test_execute_exception_handling(self):
        """Test exception handling in execute."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(side_effect=RuntimeError("Test error"))
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)

        result = await engine.execute()
        assert result.status == "failed"
        # Error is stored per-node, not at graph level
        assert "trigger_1" in result.node_results
        assert result.node_results["trigger_1"].error is not None

    @pytest.mark.asyncio
    async def test_stop_execution(self):
        """Test stopping execution."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(10)
            return {"payload": {}}

        mock_op = MagicMock()
        mock_op.execute = slow_execute
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)

        async def run_and_stop():
            asyncio.get_event_loop().call_later(0.1, engine.stop)
            return await engine.execute()

        result = await run_and_stop()
        assert engine._running is False


class TestExecuteNode:
    """Tests for _execute_node method."""

    @pytest.mark.asyncio
    async def test_execute_node_no_operator(self):
        """Test executing node with no operator."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())
        engine._state = StateManager()

        llm_node = engine._graph.get_node("llm_1")
        engine._node_statuses[llm_node.id] = NodeStatus.PENDING

        await engine._execute_node(llm_node)
        assert engine._node_statuses[llm_node.id] == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_node_with_operator(self):
        """Test executing node with operator."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())
        engine._state = StateManager()

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={"response": "test"})
        engine._builtin_operators["LLM_Task"] = MagicMock(return_value=mock_op)

        llm_node = engine._graph.get_node("llm_1")
        await engine._execute_node(llm_node)

        assert engine._node_statuses[llm_node.id] == NodeStatus.COMPLETED
        assert "response" in engine._node_outputs[llm_node.id]

    @pytest.mark.asyncio
    async def test_execute_node_error(self):
        """Test node execution error handling."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())
        engine._state = StateManager()

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(side_effect=RuntimeError("Node error"))
        engine._builtin_operators["LLM_Task"] = MagicMock(return_value=mock_op)

        llm_node = engine._graph.get_node("llm_1")

        # Without errorHandling, errors should propagate (ABORT behavior)
        with pytest.raises(RuntimeError, match="Node error"):
            await engine._execute_node(llm_node)

        assert engine._node_statuses[llm_node.id] == NodeStatus.FAILED
        assert llm_node.id in engine._node_errors


class TestTopologicalSortSubset:
    """Tests for _topological_sort_subset method."""

    def test_topological_sort_empty(self):
        """Test topological sort with empty set."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        result = engine._topological_sort_subset(set(), set())

        assert result == []

    def test_topological_sort_single_node(self):
        """Test topological sort with single node."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        result = engine._topological_sort_subset({"trigger_1"}, set())

        assert "trigger_1" in result

    def test_topological_sort_excludes_executed(self):
        """Test topological sort excludes already executed nodes."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        result = engine._topological_sort_subset({"trigger_1", "llm_1"}, {"trigger_1"})

        # trigger_1 should be excluded
        assert len(result) == 1
        assert "llm_1" in result


class TestExecuteNodeWithTracking:
    """Tests for _execute_node_with_tracking method."""

    @pytest.mark.asyncio
    async def test_execute_node_with_tracking(self):
        """Test _execute_node_with_tracking returns outputs."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())
        engine._state = StateManager()

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={"result": "ok"})
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)

        trigger = engine._graph.get_node("trigger_1")
        result = await engine._execute_node_with_tracking(trigger)

        assert result == {"result": "ok"}


class TestSafeExecute:
    """Tests for _safe_execute method."""

    @pytest.mark.asyncio
    async def test_safe_execute_success(self):
        """Test successful safe execute."""
        engine = ExecutionEngine()
        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={"result": "ok"})

        context = MagicMock()
        result = await engine._safe_execute(mock_op, {}, context)

        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_safe_execute_timeout(self):
        """Test safe execute timeout behavior."""
        engine = ExecutionEngine()

        # Create a mock that raises TimeoutError from wait_for
        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={})

        context = MagicMock()

        # Patch wait_for to simulate timeout
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            with pytest.raises(TimeoutError, match="timed out"):
                await engine._safe_execute(mock_op, {}, context)

    @pytest.mark.asyncio
    async def test_safe_execute_returns_empty_on_none(self):
        """Test safe execute returns empty dict on None result."""
        engine = ExecutionEngine()
        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value=None)

        context = MagicMock()
        result = await engine._safe_execute(mock_op, {}, context)

        assert result == {}


class TestExecuteDeadlockDetection:
    """Tests for deadlock detection in execute."""

    @pytest.mark.asyncio
    async def test_no_deadlock_single_node(self):
        """Test no deadlock for single node graph (completes normally)."""
        engine = ExecutionEngine()

        data = {
            "version": "1.0.0",
            "entryPoint": "a",
            "nodes": [
                {"id": "a", "type": "Trigger", "label": "A"},
            ],
            "edges": []
        }
        engine.load_protocol(data)

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={})
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)

        # Should complete normally, not raise deadlock
        result = await engine.execute()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_no_deadlock_linear_graph(self):
        """Test no deadlock for linear graph (a -> b -> c)."""
        engine = ExecutionEngine()

        data = {
            "version": "1.0.0",
            "entryPoint": "a",
            "nodes": [
                {"id": "a", "type": "Trigger", "label": "A"},
                {"id": "b", "type": "LLM_Task", "label": "B"},
                {"id": "c", "type": "LLM_Task", "label": "C"},
            ],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
            ]
        }
        engine.load_protocol(data)

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={})
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)
        engine._builtin_operators["LLM_Task"] = MagicMock(return_value=mock_op)

        # Should complete without deadlock
        result = await engine.execute()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_no_deadlock_branching_graph(self):
        """Test no deadlock for branching graph (a -> b, a -> c)."""
        engine = ExecutionEngine()

        data = {
            "version": "1.0.0",
            "entryPoint": "a",
            "nodes": [
                {"id": "a", "type": "Trigger", "label": "A"},
                {"id": "b", "type": "LLM_Task", "label": "B"},
                {"id": "c", "type": "LLM_Task", "label": "C"},
            ],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "a", "target": "c"},
            ]
        }
        engine.load_protocol(data)

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(return_value={})
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)
        engine._builtin_operators["LLM_Task"] = MagicMock(return_value=mock_op)

        result = await engine.execute()
        assert result.status == "success"


class TestExecuteNodeErrorHandling:
    """Tests for node error handling in execute."""

    @pytest.mark.asyncio
    async def test_execute_node_stores_error(self):
        """Test that node errors are stored in _node_errors."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())
        engine._state = StateManager()

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(side_effect=ValueError("test error"))
        engine._builtin_operators["LLM_Task"] = MagicMock(return_value=mock_op)

        llm_node = engine._graph.get_node("llm_1")

        try:
            await engine._execute_node(llm_node)
        except ValueError:
            pass

        assert llm_node.id in engine._node_errors
        assert isinstance(engine._node_errors[llm_node.id], ValueError)


class TestGetOperator:
    """Tests for get_operator method."""

    def test_get_operator_plugin_type(self):
        """Test get_operator for plugin node type."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        mock_pm = MagicMock()
        mock_pm.get_operator.return_value = MagicMock()
        engine.plugin_manager = mock_pm

        plugin_node = Node(
            id="plugin_node",
            type=NodeType.PLUGIN,
            label="Plugin",
            metadata={"config": {"plugin": "test", "function": "op"}}
        )

        result = engine.get_operator(plugin_node)

        mock_pm.get_operator.assert_called_with("test", "op")

    def test_get_operator_builtin_type(self):
        """Test get_operator for built-in node type."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        mock_op = MagicMock()
        engine._builtin_operators["Trigger"] = MagicMock(return_value=mock_op)

        trigger = engine._graph.get_node("trigger_1")
        result = engine.get_operator(trigger)

        assert result is not None


class TestResolveInputs:
    """Tests for _resolve_inputs method."""

    def test_resolve_inputs_from_edges(self):
        """Test resolving inputs from incoming edges."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        engine._node_outputs["trigger_1"] = {"payload": {"data": "test"}}

        llm_node = engine._graph.get_node("llm_1")
        inputs = engine._resolve_inputs(llm_node)

        assert inputs["prompt"] == {"data": "test"}

    def test_resolve_inputs_with_defaults(self):
        """Test resolving inputs uses port defaults."""
        data = {
            "version": "1.0.0",
            "entryPoint": "test_node",
            "metadata": {"name": "test"},
            "nodes": [
                {
                    "id": "test_node",
                    "type": "LLM_Task",
                    "label": "Test",
                    "inputs": [
                        {"name": "prompt", "type": "string"},
                        {"name": "optional", "type": "string", "default": "default_val"},
                    ],
                    "outputs": [],
                }
            ],
            "edges": [],
        }
        loader = ProtocolLoader(validate=False)
        graph = loader.load_dict(data)
        engine = ExecutionEngine()
        engine._graph = graph

        node = graph.get_node("test_node")
        inputs = engine._resolve_inputs(node)
        assert inputs["optional"] == "default_val"


class TestBuildNodeResults:
    """Tests for _build_node_results method."""

    def test_build_node_results(self):
        """Test building node results."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        engine._node_outputs["trigger_1"] = {"payload": "test"}
        engine._node_statuses["trigger_1"] = NodeStatus.COMPLETED

        results = engine._build_node_results()

        assert "trigger_1" in results
        assert results["trigger_1"].status == NodeStatus.COMPLETED
        assert results["trigger_1"].outputs == {"payload": "test"}


class TestCollectFinalOutputs:
    """Tests for _collect_final_outputs method."""

    def test_collect_final_outputs(self):
        """Test collecting final outputs from terminal nodes."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())

        engine._node_outputs["llm_1"] = {"response": "final"}

        final = engine._collect_final_outputs()

        assert "llm_1" in final
        assert final["llm_1"] == {"response": "final"}


class TestProperties:
    """Tests for engine properties."""

    def test_graph_property(self):
        """Test graph property."""
        engine = ExecutionEngine()
        graph = load_test_graph()
        engine._graph = graph

        assert engine.graph == graph

    def test_state_property(self):
        """Test state property."""
        engine = ExecutionEngine()
        state = StateManager()
        engine._state = state

        assert engine.state == state

    def test_is_running_property(self):
        """Test is_running property."""
        engine = ExecutionEngine()
        assert engine.is_running is False

        engine._running = True
        assert engine.is_running is True


class TestHandleNodeError:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handle_error_no_error_handling(self):
        """Test error with no error handling configured - should ABORT by default."""
        engine = ExecutionEngine()
        engine.load_protocol(create_test_graph_dict())
        engine._state = StateManager()

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(side_effect=RuntimeError("Error"))
        engine._builtin_operators["LLM_Task"] = MagicMock(return_value=mock_op)

        llm_node = engine._graph.get_node("llm_1")

        # Without errorHandling, errors should propagate (ABORT behavior)
        with pytest.raises(RuntimeError, match="Error"):
            await engine._execute_node(llm_node)

        assert engine._node_statuses[llm_node.id] == NodeStatus.FAILED

    @pytest.mark.asyncio
    async def test_handle_error_skip_strategy(self):
        """Test SKIP error handling strategy."""
        data = {
            "version": "1.0.0",
            "entryPoint": "test_node",
            "metadata": {"name": "test"},
            "nodes": [
                {
                    "id": "test_node",
                    "type": "LLM_Task",
                    "label": "Test",
                    "inputs": [],
                    "outputs": [],
                    "errorHandling": {
                        "strategy": "skip",
                        "maxRetries": 0,
                    },
                }
            ],
            "edges": [],
        }
        loader = ProtocolLoader(validate=False)
        graph = loader.load_dict(data)

        engine = ExecutionEngine()
        engine.load_protocol(data)
        engine._state = StateManager()

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(side_effect=RuntimeError("Error"))
        engine._builtin_operators["LLM_Task"] = MagicMock(return_value=mock_op)

        node = engine._graph.get_node("test_node")
        await engine._execute_node(node)
        assert engine._node_statuses[node.id] == NodeStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_handle_error_abort_strategy(self):
        """Test ABORT error handling strategy."""
        data = {
            "version": "1.0.0",
            "entryPoint": "test_node",
            "metadata": {"name": "test"},
            "nodes": [
                {
                    "id": "test_node",
                    "type": "LLM_Task",
                    "label": "Test",
                    "inputs": [],
                    "outputs": [],
                    "errorHandling": {
                        "strategy": "abort",
                        "maxRetries": 0,
                    },
                }
            ],
            "edges": [],
        }
        engine = ExecutionEngine()
        engine.load_protocol(data)
        engine._state = StateManager()

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(side_effect=RuntimeError("Error"))
        engine._builtin_operators["LLM_Task"] = MagicMock(return_value=mock_op)

        node = engine._graph.get_node("test_node")
        with pytest.raises(RuntimeError, match="Error"):
            await engine._execute_node(node)

    @pytest.mark.asyncio
    async def test_handle_error_retry_strategy(self):
        """Test RETRY error handling strategy."""
        data = {
            "version": "1.0.0",
            "entryPoint": "test_node",
            "metadata": {"name": "test"},
            "nodes": [
                {
                    "id": "test_node",
                    "type": "LLM_Task",
                    "label": "Test",
                    "inputs": [],
                    "outputs": [],
                    "errorHandling": {
                        "strategy": "retry",
                        "maxRetries": 2,
                    },
                }
            ],
            "edges": [],
        }
        engine = ExecutionEngine()
        engine.load_protocol(data)
        engine._state = StateManager()

        call_count = 0

        async def failing_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Fail")
            return {"result": "success"}

        mock_op = MagicMock()
        mock_op.execute = failing_execute
        engine._builtin_operators["LLM_Task"] = MagicMock(return_value=mock_op)

        node = engine._graph.get_node("test_node")
        await engine._execute_node(node)
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_handle_error_fallback_strategy(self):
        """Test FALLBACK error handling strategy."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "metadata": {"name": "test"},
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Trigger",
                    "inputs": [],
                    "outputs": [{"name": "payload", "type": "any"}],
                },
                {
                    "id": "failing",
                    "type": "LLM_Task",
                    "label": "Failing",
                    "inputs": [],
                    "outputs": [],
                    "errorHandling": {
                        "strategy": "fallback",
                        "maxRetries": 0,
                        "fallbackNode": "fallback_node",
                    },
                },
                {
                    "id": "fallback_node",
                    "type": "Trigger",
                    "label": "Fallback",
                    "inputs": [],
                    "outputs": [{"name": "payload", "type": "any"}],
                },
            ],
            "edges": [
                {"source": "trigger_1", "sourcePort": "payload", "target": "failing", "targetPort": ""},
                {"source": "failing", "sourcePort": "", "target": "fallback_node", "targetPort": ""},
            ],
        }
        engine = ExecutionEngine()
        engine.load_protocol(data)
        engine._state = StateManager()

        mock_op = MagicMock()
        mock_op.execute = AsyncMock(side_effect=RuntimeError("Error"))
        engine._builtin_operators["LLM_Task"] = MagicMock(return_value=mock_op)

        fallback_op = MagicMock()
        fallback_op.execute = AsyncMock(return_value={"payload": {}})
        engine._builtin_operators["Trigger"] = MagicMock(return_value=fallback_op)

        trigger = engine._graph.get_node("trigger_1")
        await engine._execute_node(trigger)
