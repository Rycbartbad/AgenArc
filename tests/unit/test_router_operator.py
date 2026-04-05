"""Unit tests for operators/router.py."""

import pytest
from agenarc.operators.router import RouterOperator
from agenarc.protocol.schema import Condition, ConditionOperator
from agenarc.engine.state import StateManager, ExecutionContext


def create_context():
    """Create a test execution context."""
    sm = StateManager()
    sm.initialize("test_exec", "test_graph")
    return ExecutionContext(sm)


class TestRouterOperator:
    """Tests for RouterOperator."""

    def test_name(self):
        """Test operator name."""
        op = RouterOperator()
        assert op.name == "builtin.router"

    def test_description(self):
        """Test operator description."""
        op = RouterOperator()
        assert op.description == "Route execution based on condition expressions"

    def test_input_ports(self):
        """Test operator input ports."""
        op = RouterOperator()
        ports = op.get_input_ports()
        assert len(ports) == 1
        assert ports[0].name == "input"

    def test_output_ports(self):
        """Test operator output ports."""
        op = RouterOperator()
        ports = op.get_output_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "output_A" in port_names
        assert "output_B" in port_names

    @pytest.mark.asyncio
    async def test_route_to_a_when_condition_matches(self):
        """Test routing to output_A when condition matches."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.EQ,
                value="yes",
                output="output_A"
            )
        ])
        ctx.set("_router_default", "B")

        result = await op.execute({"input": "yes"}, ctx)

        assert result["output_A"] == "yes"
        assert result["output_B"] is None

    @pytest.mark.asyncio
    async def test_route_to_b_when_condition_matches(self):
        """Test routing to output_B when condition matches."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.EQ,
                value="no",
                output="output_B"
            )
        ])
        ctx.set("_router_default", "A")

        result = await op.execute({"input": "no"}, ctx)

        assert result["output_A"] is None
        assert result["output_B"] == "no"

    @pytest.mark.asyncio
    async def test_default_route_when_no_match(self):
        """Test default routing when no condition matches."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.EQ,
                value="yes",
                output="output_A"
            )
        ])
        ctx.set("_router_default", "B")

        result = await op.execute({"input": "maybe"}, ctx)

        assert result["output_A"] is None
        assert result["output_B"] == "maybe"

    @pytest.mark.asyncio
    async def test_greater_than_condition(self):
        """Test greater than comparison."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.GT,
                value=10,
                output="output_A"
            )
        ])

        result = await op.execute({"input": 15}, ctx)

        assert result["output_A"] == 15
        assert result["output_B"] is None

    @pytest.mark.asyncio
    async def test_less_than_condition(self):
        """Test less than comparison."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.LT,
                value=10,
                output="output_A"
            )
        ])

        result = await op.execute({"input": 5}, ctx)

        assert result["output_A"] == 5
        assert result["output_B"] is None

    @pytest.mark.asyncio
    async def test_contains_condition(self):
        """Test contains comparison for strings."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.CONTAINS,
                value="test",
                output="output_A"
            )
        ])

        result = await op.execute({"input": "this is a test string"}, ctx)

        assert result["output_A"] == "this is a test string"
        assert result["output_B"] is None

    @pytest.mark.asyncio
    async def test_in_condition(self):
        """Test in comparison."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.IN,
                value=["a", "b", "c"],
                output="output_A"
            )
        ])

        result = await op.execute({"input": "b"}, ctx)

        assert result["output_A"] == "b"
        assert result["output_B"] is None

    @pytest.mark.asyncio
    async def test_exists_condition(self):
        """Test exists comparison."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.EXISTS,
                value=None,
                output="output_A"
            )
        ])

        result = await op.execute({"input": "something"}, ctx)

        assert result["output_A"] == "something"
        assert result["output_B"] is None

    @pytest.mark.asyncio
    async def test_not_exists_condition(self):
        """Test not exists comparison."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.NOT_EXISTS,
                value=None,
                output="output_A"
            )
        ])

        result = await op.execute({"input": None}, ctx)

        assert result["output_A"] is None
        assert result["output_B"] is None


class TestRouterConditionComparison:
    """Tests for different condition comparison operators."""

    @pytest.mark.asyncio
    async def test_eq_operator(self):
        """Test equality operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.EQ, value=42, output="A")
        ])

        result = await op.execute({"input": 42}, ctx)
        assert result["output_A"] == 42

    @pytest.mark.asyncio
    async def test_ne_operator(self):
        """Test not equal operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.NE, value=42, output="A")
        ])

        result = await op.execute({"input": 100}, ctx)
        assert result["output_A"] == 100

    @pytest.mark.asyncio
    async def test_gte_operator(self):
        """Test greater than or equal operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.GTE, value=10, output="A")
        ])

        result = await op.execute({"input": 10}, ctx)
        assert result["output_A"] == 10

    @pytest.mark.asyncio
    async def test_lte_operator(self):
        """Test less than or equal operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.LTE, value=10, output="A")
        ])

        result = await op.execute({"input": 10}, ctx)
        assert result["output_A"] == 10

    @pytest.mark.asyncio
    async def test_starts_with_operator(self):
        """Test startsWith operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.STARTS_WITH, value="hello", output="A")
        ])

        result = await op.execute({"input": "hello world"}, ctx)
        assert result["output_A"] == "hello world"

    @pytest.mark.asyncio
    async def test_ends_with_operator(self):
        """Test endsWith operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.ENDS_WITH, value="world", output="A")
        ])

        result = await op.execute({"input": "hello world"}, ctx)
        assert result["output_A"] == "hello world"

    @pytest.mark.asyncio
    async def test_not_in_operator(self):
        """Test notIn operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.NOT_IN, value=["a", "b"], output="A")
        ])

        result = await op.execute({"input": "c"}, ctx)
        assert result["output_A"] == "c"
