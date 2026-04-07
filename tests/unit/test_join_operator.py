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
        """Test operator input ports."""
        op = JoinOperator()
        ports = op.get_input_ports()
        port_names = {p.name for p in ports}
        assert "input_A" in port_names
        assert "input_B" in port_names
        assert "strategy" in port_names

    def test_output_ports(self):
        """Test operator output ports."""
        op = JoinOperator()
        ports = op.get_output_ports()
        port_names = {p.name for p in ports}
        assert "output" in port_names
        assert "inputs" in port_names

    @pytest.mark.asyncio
    async def test_first_strategy_with_A(self):
        """Test first strategy returns input_A when present."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": "A",
            "input_B": "B",
            "strategy": "first"
        }, ctx)

        assert result["output"] == "A"
        assert "A" in result["inputs"]

    @pytest.mark.asyncio
    async def test_first_strategy_fallback_to_B(self):
        """Test first strategy returns input_B when A is None."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": None,
            "input_B": "B",
            "strategy": "first"
        }, ctx)

        assert result["output"] == "B"

    @pytest.mark.asyncio
    async def test_last_strategy(self):
        """Test last strategy returns input_B."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": "A",
            "input_B": "B",
            "strategy": "last"
        }, ctx)

        assert result["output"] == "B"

    @pytest.mark.asyncio
    async def test_merge_strategy(self):
        """Test merge strategy returns dict with both inputs."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": "A",
            "input_B": "B",
            "strategy": "merge"
        }, ctx)

        assert result["output"] == {"input_A": "A", "input_B": "B"}

    @pytest.mark.asyncio
    async def test_concat_strategy_lists(self):
        """Test concat strategy with lists."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": [1, 2],
            "input_B": [3, 4],
            "strategy": "concat"
        }, ctx)

        assert result["output"] == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_concat_strategy_mixed(self):
        """Test concat strategy with mixed types."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": "scalar",
            "input_B": [3, 4],
            "strategy": "concat"
        }, ctx)

        assert result["output"] == ["scalar", 3, 4]

    @pytest.mark.asyncio
    async def test_all_strategy(self):
        """Test all strategy returns all inputs as list."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": "A",
            "input_B": "B",
            "strategy": "all"
        }, ctx)

        assert result["output"] == ["A", "B"]

    @pytest.mark.asyncio
    async def test_all_strategy_filters_none(self):
        """Test all strategy filters out None inputs."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": "A",
            "input_B": None,
            "strategy": "all"
        }, ctx)

        assert result["output"] == ["A"]
        assert result["inputs"] == ["A"]

    @pytest.mark.asyncio
    async def test_default_strategy_is_first(self):
        """Test default strategy is 'first'."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": "A",
            "input_B": "B"
        }, ctx)

        assert result["output"] == "A"

    @pytest.mark.asyncio
    async def test_unknown_strategy_defaults_to_first(self):
        """Test unknown strategy defaults to first."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": "A",
            "input_B": "B",
            "strategy": "unknown"
        }, ctx)

        assert result["output"] == "A"

    @pytest.mark.asyncio
    async def test_inputs_output_always_list(self):
        """Test that inputs output is always a list."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": None,
            "input_B": None,
            "strategy": "first"
        }, ctx)

        assert result["inputs"] == []

    @pytest.mark.asyncio
    async def test_both_none(self):
        """Test with both inputs None."""
        op = JoinOperator()
        ctx = create_context()

        result = await op.execute({
            "input_A": None,
            "input_B": None,
            "strategy": "merge"
        }, ctx)

        assert result["output"] == {"input_A": None, "input_B": None}


class TestJoinOperatorConcat:
    """Tests for _concat helper method."""

    def test_concat_empty(self):
        """Test concat with empty input."""
        op = JoinOperator()
        result = op._concat([])
        assert result == []

    def test_concat_scalars(self):
        """Test concat with scalar values."""
        op = JoinOperator()
        result = op._concat([1, 2, 3])
        assert result == [1, 2, 3]

    def test_concat_mixed(self):
        """Test concat with mixed lists and scalars."""
        op = JoinOperator()
        result = op._concat([[1, 2], 3, [4, 5]])
        assert result == [1, 2, 3, 4, 5]

    def test_concat_nested_lists(self):
        """Test concat flattens one level."""
        op = JoinOperator()
        result = op._concat([[1, [2]], 3])
        assert result == [1, [2], 3]
