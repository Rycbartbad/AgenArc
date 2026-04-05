"""
Operator Interface

Standard interface for all operators (plugins) in AgenArc.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from agenarc.engine.state import ExecutionContext
    from agenarc.protocol.schema import Port


class IOperator(ABC):
    """
    Standard interface for all operators.

    All operators must implement this interface to be used in the engine.

    Usage:
        class MyOperator(IOperator):
            @property
            def name(self) -> str:
                return "my_operator"

            async def execute(self, inputs, context):
                return {"result": inputs["x"] * 2}
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Globally unique operator name.

        Format: plugin_name.operator_name
        Example: "builtin.trigger", "openai.chat_complete"
        """
        pass

    @property
    def version(self) -> str:
        """
        Semantic version of operator.

        Default: "1.0.0"
        """
        return "1.0.0"

    @property
    def description(self) -> str:
        """
        Human-readable description of the operator.

        Default: empty string
        """
        return ""

    @abstractmethod
    def get_input_ports(self) -> List["Port"]:
        """
        Define input ports for this operator.

        Returns:
            List of Port objects defining inputs
        """
        pass

    @abstractmethod
    def get_output_ports(self) -> List["Port"]:
        """
        Define output ports for this operator.

        Returns:
            List of Port objects defining outputs
        """
        pass

    @abstractmethod
    async def execute(
        self,
        inputs: Dict[str, Any],
        context: "ExecutionContext"
    ) -> Dict[str, Any]:
        """
        Execute the operator.

        Args:
            inputs: Resolved input values from connected nodes
            context: Global execution context

        Returns:
            Dictionary mapping output port names to values

        Raises:
            Any exception to signal error (handled by engine)
        """
        pass

    async def validate(self, inputs: Dict[str, Any]) -> bool:
        """
        Validate inputs before execution.

        Override for custom validation logic.

        Args:
            inputs: Input values to validate

        Returns:
            True if valid, False otherwise
        """
        required_ports = self.get_input_ports()
        required_names = {p.name for p in required_ports if p.default is None}

        # Check all required inputs are present
        return all(key in inputs for key in required_names)

    async def prepare(self) -> None:
        """
        Called once before execution starts.

        Use for initialization (e.g., loading models, opening connections).
        """
        pass

    async def cleanup(self) -> None:
        """
        Called after execution completes.

        Use for cleanup (e.g., closing connections, releasing resources).
        """
        pass
