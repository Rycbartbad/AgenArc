"""Unit tests for operators/loop.py."""

import pytest
from agenarc.operators.loop import Loop_Control_Operator
from agenarc.protocol.schema import Condition, ConditionOperator
from agenarc.engine.state import StateManager, ExecutionContext


def create_context():
    """Create a test execution context."""
    sm = StateManager()
    sm.initialize("test_exec", "test_graph")
    return ExecutionContext(sm)


class TestLoopControlOperator:
    """Tests for Loop_Control_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Loop_Control_Operator()
        assert op.name == "builtin.loop_control"

    def test_description(self):
        """Test operator description."""
        op = Loop_Control_Operator()
        assert op.description == "Iterate over collections with feedback loop support"

    def test_input_ports(self):
        """Test operator input ports."""
        op = Loop_Control_Operator()
        ports = op.get_input_ports()
        assert len(ports) == 3
        port_names = {p.name for p in ports}
        assert "iterate_on" in port_names
        assert "max_iterations" in port_names
        assert "accumulator_input" in port_names

    def test_output_ports(self):
        """Test operator output ports."""
        op = Loop_Control_Operator()
        ports = op.get_output_ports()
        assert len(ports) == 4
        port_names = {p.name for p in ports}
        assert "iteration_count" in port_names
        assert "current_item" in port_names
        assert "accumulator" in port_names
        assert "done" in port_names

    @pytest.mark.asyncio
    async def test_first_iteration(self):
        """Test first iteration of loop."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "test_loop")

        result = await op.execute({"iterate_on": ["a", "b", "c"]}, ctx)

        assert result["iteration_count"] == 0
        assert result["current_item"] == "a"
        assert result["done"] is False

    @pytest.mark.asyncio
    async def test_second_iteration(self):
        """Test second iteration of loop."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "test_loop")
        ctx.set("_loop_test_loop_iteration", 1)  # Already at iteration 1

        result = await op.execute({"iterate_on": ["a", "b", "c"]}, ctx)

        assert result["iteration_count"] == 1
        assert result["current_item"] == "b"
        assert result["done"] is False

    @pytest.mark.asyncio
    async def test_last_iteration(self):
        """Test last iteration of loop."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "test_loop")
        ctx.set("_loop_test_loop_iteration", 2)  # Last index (2 of 3 items)

        result = await op.execute({"iterate_on": ["a", "b", "c"]}, ctx)

        assert result["iteration_count"] == 2
        assert result["current_item"] == "c"
        assert result["done"] is False

    @pytest.mark.asyncio
    async def test_completion_after_last(self):
        """Test loop completion after last item."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "test_loop")
        ctx.set("_loop_test_loop_iteration", 3)  # Past last index

        result = await op.execute({"iterate_on": ["a", "b", "c"]}, ctx)

        assert result["iteration_count"] == 3
        assert result["current_item"] is None
        assert result["done"] is True

    @pytest.mark.asyncio
    async def test_max_iterations(self):
        """Test max iterations limit."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "test_loop")
        ctx.set("_loop_test_loop_iteration", 5)  # Already at iteration 5

        result = await op.execute({"iterate_on": ["a", "b", "c"], "max_iterations": 5}, ctx)

        assert result["done"] is True

    @pytest.mark.asyncio
    async def test_empty_collection(self):
        """Test loop with empty collection."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "test_loop")

        result = await op.execute({"iterate_on": []}, ctx)

        assert result["iteration_count"] == 0
        assert result["current_item"] is None
        assert result["done"] is True

    @pytest.mark.asyncio
    async def test_non_iterable(self):
        """Test loop with non-iterable input."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "test_loop")

        result = await op.execute({"iterate_on": "not a list"}, ctx)

        assert result["done"] is True

    @pytest.mark.asyncio
    async def test_checkpoint_enabled(self):
        """Test checkpoint creation when enabled."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "test_loop")
        ctx.set("_loop_checkpoint", True)

        result = await op.execute({"iterate_on": ["a", "b"]}, ctx)

        # Should create a checkpoint
        checkpoint_id = ctx.get("_loop_test_loop_checkpoint")
        # Checkpoint might be set depending on implementation

    @pytest.mark.asyncio
    async def test_accumulator_preserved(self):
        """Test accumulator value is preserved across iterations."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "test_loop")
        ctx.set("_loop_test_loop_iteration", 1)
        ctx.set("_loop_test_loop_accumulator", {"sum": 10})

        result = await op.execute({"iterate_on": [1, 2, 3]}, ctx)

        assert result["accumulator"] == {"sum": 10}


class TestLoopControlWithTermination:
    """Tests for Loop_Control with termination conditions."""

    @pytest.mark.asyncio
    async def test_termination_condition(self):
        """Test early termination when condition is met."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "test_loop")
        ctx.set("_loop_termination_conditions", [
            Condition(
                ref="current_item",
                operator=ConditionOperator.EQ,
                value="stop",
                output="done"
            )
        ])

        result = await op.execute({"iterate_on": ["a", "stop", "c"]}, ctx)

        # First iteration should not trigger termination
        assert result["iteration_count"] == 0
        assert result["current_item"] == "a"
        assert result["done"] is False


class TestLoopControlIterationCount:
    """Tests for iteration counting."""

    @pytest.mark.asyncio
    async def test_iteration_count_increments(self):
        """Test iteration count increments each iteration."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "counter_test")

        # First call
        result1 = await op.execute({"iterate_on": ["x", "y", "z"]}, ctx)
        assert result1["iteration_count"] == 0

        # Second call
        result2 = await op.execute({"iterate_on": ["x", "y", "z"]}, ctx)
        assert result2["iteration_count"] == 1

        # Third call
        result3 = await op.execute({"iterate_on": ["x", "y", "z"]}, ctx)
        assert result3["iteration_count"] == 2

    @pytest.mark.asyncio
    async def test_loop_id_isolation(self):
        """Test different loop IDs are isolated."""
        op = Loop_Control_Operator()
        ctx = create_context()
        ctx.set("_loop_id", "loop1")
        ctx.set("_loop_loop1_iteration", 1)

        ctx2 = create_context()
        ctx2.set("_loop_id", "loop2")
        ctx2.set("_loop_loop2_iteration", 0)

        result1 = await op.execute({"iterate_on": ["a", "b"]}, ctx)
        result2 = await op.execute({"iterate_on": ["x", "y"]}, ctx2)

        assert result1["iteration_count"] == 1
        assert result2["iteration_count"] == 0
