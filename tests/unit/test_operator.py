"""Unit tests for operators/operator.py."""

import pytest
from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port
from agenarc.engine.state import StateManager, ExecutionContext


class ConcreteOperator(IOperator):
    """Concrete implementation for testing."""

    def __init__(self, name="test.operator"):
        self._name = name
        self._version = "1.0.0"
        self._description = "Test operator"

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def description(self) -> str:
        return self._description

    def get_input_ports(self) -> list[Port]:
        return [
            Port(name="input1", type="string", description="First input"),
            Port(name="input2", type="number", description="Second input", default=42),
        ]

    def get_output_ports(self) -> list[Port]:
        return [
            Port(name="output", type="string", description="The output"),
        ]

    async def execute(self, inputs, context):
        return {"output": f"processed: {inputs.get('input1', '')}"}


class TestIOperatorInterface:
    """Tests for IOperator abstract base class."""

    def test_name_property_required(self):
        """Test name property is required."""
        operator = ConcreteOperator()
        assert operator.name == "test.operator"

    def test_version_property_default(self):
        """Test version property has default."""
        operator = ConcreteOperator()
        assert operator.version == "1.0.0"

    def test_description_property_default(self):
        """Test description property has default."""
        operator = ConcreteOperator()
        assert operator.description == "Test operator"

    def test_get_input_ports(self):
        """Test get_input_ports returns list of ports."""
        operator = ConcreteOperator()
        ports = operator.get_input_ports()
        assert len(ports) == 2
        assert ports[0].name == "input1"
        assert ports[1].name == "input2"

    def test_get_output_ports(self):
        """Test get_output_ports returns list of ports."""
        operator = ConcreteOperator()
        ports = operator.get_output_ports()
        assert len(ports) == 1
        assert ports[0].name == "output"

    def test_execute_method_required(self):
        """Test execute is an async method."""
        import asyncio
        operator = ConcreteOperator()
        sm = StateManager()
        sm.initialize("test_exec", "test_graph")
        context = ExecutionContext(sm)

        result = asyncio.run(operator.execute({"input1": "test"}, context))
        assert result["output"] == "processed: test"


class TestOperatorValidate:
    """Tests for operator validate method."""

    @pytest.mark.asyncio
    async def test_validate_with_required_inputs(self):
        """Test validate passes when required inputs present."""
        operator = ConcreteOperator()
        result = await operator.validate({"input1": "value"})
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_fails_without_required_inputs(self):
        """Test validate fails when required inputs missing."""
        operator = ConcreteOperator()
        # input1 is required, input2 has default
        result = await operator.validate({})
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_with_all_inputs(self):
        """Test validate passes with all inputs."""
        operator = ConcreteOperator()
        result = await operator.validate({"input1": "value", "input2": 100})
        assert result is True


class TestOperatorPrepare:
    """Tests for operator prepare/cleanup lifecycle."""

    def test_prepare_default_is_noop(self):
        """Test prepare default implementation is a no-op."""
        import asyncio
        operator = ConcreteOperator()
        # Should not raise
        asyncio.run(operator.prepare())

    def test_cleanup_default_is_noop(self):
        """Test cleanup default implementation is a no-op."""
        import asyncio
        operator = ConcreteOperator()
        # Should not raise
        asyncio.run(operator.cleanup())
