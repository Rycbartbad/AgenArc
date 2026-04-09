"""Unit tests for operators/join.py."""

import pytest
from agenarc.operators.join import JoinOperator
from agenarc.engine.state import StateManager, ExecutionContext


def create_context():
    """Create a test execution context."""
    sm = StateManager()
    sm.initialize("test_exec", "test_graph")
    return ExecutionContext(sm)


class TestJoinOperator:
    """Tests for JoinOperator."""

    def test_name(self):
        """Test operator name."""
        op = JoinOperator()
        assert op.name == "builtin.join"

    def test_description(self):
        """Test operator description."""
        op = JoinOperator()
        assert "join" in op.description.lower()

    def test_input_ports(self):
        """Test operator input ports - Join has no fixed ports."""
        op = JoinOperator()
        ports = op.get_input_ports()
        # Join does not declare fixed input ports
        assert len(ports) == 0

    def test_output_ports(self):
        """Test operator output ports."""
        op = JoinOperator()
        ports = op.get_output_ports()
        port_names = {p.name for p in ports}
        assert "output" in port_names

    @pytest.mark.asyncio
    async def test_merge_strategy(self):
        """Test merge strategy returns dict of all inputs."""
        op = JoinOperator()
        ctx = create_context()

        # Simulate incoming edges from branch_A and branch_B
        ctx.set("_incoming_edges", [
            {"source": "branch_A", "sourcePort": "output"},
            {"source": "branch_B", "sourcePort": "output"},
        ])
        ctx.set("_join_strategy", "merge")
        ctx.set("_node_id", "join_1")

        # Store outputs in context (simulating what branch nodes would do)
        ctx.set("nodes.branch_A.output", "value_a")
        ctx.set("nodes.branch_B.output", "value_b")

        result = await op.execute({}, ctx)

        assert result["output"] == {
            "branch_A.output": "value_a",
            "branch_B.output": "value_b"
        }

    @pytest.mark.asyncio
    async def test_first_strategy(self):
        """Test first strategy returns first input."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [
            {"source": "A", "sourcePort": "data"},
            {"source": "B", "sourcePort": "data"},
        ])
        ctx.set("_join_strategy", "first")
        ctx.set("_node_id", "join_1")

        ctx.set("nodes.A.data", "first_value")
        ctx.set("nodes.B.data", "second_value")

        result = await op.execute({}, ctx)

        assert result["output"] == "first_value"

    @pytest.mark.asyncio
    async def test_last_strategy(self):
        """Test last strategy returns last input."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [
            {"source": "A", "sourcePort": "data"},
            {"source": "B", "sourcePort": "data"},
        ])
        ctx.set("_join_strategy", "last")
        ctx.set("_node_id", "join_1")

        ctx.set("nodes.A.data", "first")
        ctx.set("nodes.B.data", "last")

        result = await op.execute({}, ctx)

        assert result["output"] == "last"

    @pytest.mark.asyncio
    async def test_concat_strategy(self):
        """Test concat strategy concatenates lists."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [
            {"source": "A", "sourcePort": "items"},
            {"source": "B", "sourcePort": "items"},
        ])
        ctx.set("_join_strategy", "concat")
        ctx.set("_node_id", "join_1")

        ctx.set("nodes.A.items", [1, 2])
        ctx.set("nodes.B.items", [3, 4])

        result = await op.execute({}, ctx)

        assert result["output"] == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_concat_strategy_mixed(self):
        """Test concat with mixed scalars and lists."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [
            {"source": "A", "sourcePort": "data"},
            {"source": "B", "sourcePort": "data"},
        ])
        ctx.set("_join_strategy", "concat")
        ctx.set("_node_id", "join_1")

        ctx.set("nodes.A.data", "scalar")
        ctx.set("nodes.B.data", [3, 4])

        result = await op.execute({}, ctx)

        assert result["output"] == ["scalar", 3, 4]

    @pytest.mark.asyncio
    async def test_default_strategy_is_merge(self):
        """Test default strategy is 'merge'."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [
            {"source": "A", "sourcePort": "out"},
        ])
        # Don't set _join_strategy - should default to merge
        ctx.set("_node_id", "join_1")

        ctx.set("nodes.A.out", "value_a")

        result = await op.execute({}, ctx)

        # Default is merge, so should return dict
        assert result["output"] == {"A.out": "value_a"}

    @pytest.mark.asyncio
    async def test_empty_incoming_edges(self):
        """Test with no incoming edges."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [])
        ctx.set("_join_strategy", "first")
        ctx.set("_node_id", "join_1")

        result = await op.execute({}, ctx)

        assert result["output"] is None

    @pytest.mark.asyncio
    async def test_missing_source_data(self):
        """Test when some source nodes have no data yet."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [
            {"source": "A", "sourcePort": "data"},
            {"source": "B", "sourcePort": "data"},
        ])
        ctx.set("_join_strategy", "merge")
        ctx.set("_node_id", "join_1")

        # Only set A's data, B hasn't executed yet
        ctx.set("nodes.A.data", "value_a")

        result = await op.execute({}, ctx)

        # Only A's data is collected
        assert result["output"] == {"A.data": "value_a"}

    @pytest.mark.asyncio
    async def test_node_id_in_context(self):
        """Test that node_id is used in context key generation."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [
            {"source": "src", "sourcePort": "result"},
        ])
        ctx.set("_join_strategy", "merge")
        ctx.set("_node_id", "my_join_node")

        ctx.set("nodes.src.result", "test_value")

        result = await op.execute({}, ctx)

        assert result["output"] == {"src.result": "test_value"}

    @pytest.mark.asyncio
    async def test_edge_without_source_port(self):
        """Test that edges without sourcePort are skipped."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [
            {"source": "A", "sourcePort": "data"},
            {"source": "B"},  # No sourcePort
        ])
        ctx.set("_join_strategy", "merge")
        ctx.set("_node_id", "join_1")

        ctx.set("nodes.A.data", "value_a")
        # B has no sourcePort, should be skipped

        result = await op.execute({}, ctx)

        assert result["output"] == {"A.data": "value_a"}


class TestJoinOperatorContextBased:
    """Tests for Join with context-based edge information."""

    @pytest.mark.asyncio
    async def test_three_branch_merge(self):
        """Test merging three parallel branches."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [
            {"source": "branch_1", "sourcePort": "output"},
            {"source": "branch_2", "sourcePort": "output"},
            {"source": "branch_3", "sourcePort": "output"},
        ])
        ctx.set("_join_strategy", "merge")
        ctx.set("_node_id", "join_1")

        ctx.set("nodes.branch_1.output", {"id": 1})
        ctx.set("nodes.branch_2.output", {"id": 2})
        ctx.set("nodes.branch_3.output", {"id": 3})

        result = await op.execute({}, ctx)

        assert len(result["output"]) == 3
        assert result["output"]["branch_1.output"] == {"id": 1}
        assert result["output"]["branch_2.output"] == {"id": 2}
        assert result["output"]["branch_3.output"] == {"id": 3}

    @pytest.mark.asyncio
    async def test_three_branch_concat(self):
        """Test concatenating three parallel branches."""
        op = JoinOperator()
        ctx = create_context()

        ctx.set("_incoming_edges", [
            {"source": "branch_1", "sourcePort": "items"},
            {"source": "branch_2", "sourcePort": "items"},
            {"source": "branch_3", "sourcePort": "items"},
        ])
        ctx.set("_join_strategy", "concat")
        ctx.set("_node_id", "join_1")

        ctx.set("nodes.branch_1.items", [1])
        ctx.set("nodes.branch_2.items", [2])
        ctx.set("nodes.branch_3.items", [3])

        result = await op.execute({}, ctx)

        assert result["output"] == [1, 2, 3]
