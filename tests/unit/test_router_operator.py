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
        # Router does not declare fixed output ports.
        # Output ports are determined by edges with matching sourcePort values.
        assert len(ports) == 0

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
                output="A"
            )
        ])
        ctx.set("_router_default", "B")

        result = await op.execute({"input": "yes"}, ctx)

        # Router returns _selected indicating which output was chosen
        assert result["_selected"] == ["A"]

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
                output="B"
            )
        ])
        ctx.set("_router_default", "A")

        result = await op.execute({"input": "no"}, ctx)

        assert result["_selected"] == ["B"]

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
                output="A"
            )
        ])
        ctx.set("_router_default", "B")

        result = await op.execute({"input": "maybe"}, ctx)

        assert result["_selected"] == ["B"]

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
                output="yes"
            )
        ])

        result = await op.execute({"input": 15}, ctx)

        assert result["_selected"] == ["yes"]

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
                output="yes"
            )
        ])

        result = await op.execute({"input": 5}, ctx)

        assert result["_selected"] == ["yes"]

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
                output="match"
            )
        ])

        result = await op.execute({"input": "this is a test string"}, ctx)

        assert result["_selected"] == ["match"]

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
                output="found"
            )
        ])

        result = await op.execute({"input": "b"}, ctx)

        assert result["_selected"] == ["found"]

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
                output="exists"
            )
        ])

        result = await op.execute({"input": "something"}, ctx)

        assert result["_selected"] == ["exists"]

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
                output="not_exists"
            )
        ])

        result = await op.execute({"input": None}, ctx)

        assert result["_selected"] == ["not_exists"]


class TestRouterConditionComparison:
    """Tests for different condition comparison operators."""

    @pytest.mark.asyncio
    async def test_eq_operator(self):
        """Test equality operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.EQ, value=42, output="yes")
        ])

        result = await op.execute({"input": 42}, ctx)
        assert result["_selected"] == ["yes"]

    @pytest.mark.asyncio
    async def test_ne_operator(self):
        """Test not equal operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.NE, value=42, output="yes")
        ])

        result = await op.execute({"input": 100}, ctx)
        assert result["_selected"] == ["yes"]

    @pytest.mark.asyncio
    async def test_gte_operator(self):
        """Test greater than or equal operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.GTE, value=10, output="yes")
        ])

        result = await op.execute({"input": 10}, ctx)
        assert result["_selected"] == ["yes"]

    @pytest.mark.asyncio
    async def test_lte_operator(self):
        """Test less than or equal operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.LTE, value=10, output="yes")
        ])

        result = await op.execute({"input": 10}, ctx)
        assert result["_selected"] == ["yes"]

    @pytest.mark.asyncio
    async def test_starts_with_operator(self):
        """Test startsWith operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.STARTS_WITH, value="hello", output="yes")
        ])

        result = await op.execute({"input": "hello world"}, ctx)
        assert result["_selected"] == ["yes"]

    @pytest.mark.asyncio
    async def test_ends_with_operator(self):
        """Test endsWith operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.ENDS_WITH, value="world", output="yes")
        ])

        result = await op.execute({"input": "hello world"}, ctx)
        assert result["_selected"] == ["yes"]

    @pytest.mark.asyncio
    async def test_not_in_operator(self):
        """Test notIn operator."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(ref="input", operator=ConditionOperator.NOT_IN, value=["a", "b"], output="yes")
        ])

        result = await op.execute({"input": "c"}, ctx)
        assert result["_selected"] == ["yes"]


class TestRouterDynamicOutput:
    """Tests for Router dynamic output (assembly-style jump)."""

    @pytest.mark.asyncio
    async def test_node_id_as_output(self):
        """Test using node ID as output for loops."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.GT,
                value=0,
                output="counter_inc"  # Node ID as output label
            )
        ])
        ctx.set("_router_default", "exit")

        result = await op.execute({"input": 5}, ctx)

        # Router returns _selected with the output label
        assert result["_selected"] == ["counter_inc"]

    @pytest.mark.asyncio
    async def test_default_with_node_id(self):
        """Test default routing with node ID output."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="input",
                operator=ConditionOperator.EQ,
                value="yes",
                output="loop"
            )
        ])
        ctx.set("_router_default", "exit_node")

        result = await op.execute({"input": "no"}, ctx)

        # No match, should use default
        assert result["_selected"] == ["exit_node"]

    @pytest.mark.asyncio
    async def test_context_ref_as_output_label(self):
        """Test that output can be any string identifier."""
        op = RouterOperator()
        ctx = create_context()
        ctx.set("_router_conditions", [
            Condition(
                ref="context.loop_count",
                operator=ConditionOperator.LT,
                value=10,
                output="iterate"
            )
        ])
        ctx.set("_router_default", "done")
        ctx.set("loop_count", 5)

        result = await op.execute({"input": "anything"}, ctx)

        assert result["_selected"] == ["iterate"]
