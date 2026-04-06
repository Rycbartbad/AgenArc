"""
Join Operator for AgenArc

Provides explicit multi-input synchronization and merging strategies.
"""

from typing import Any, Dict, List

from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port


class JoinOperator(IOperator):
    """
    Join Operator - synchronizes multiple inputs and merges them.

    Used when a node has multiple incoming edges and needs to explicitly
    wait for all predecessors and merge their outputs.

    Strategies:
        - first: Return the first input that arrives
        - last: Return the last input that arrives
        - merge: Merge all inputs into a dict keyed by source node ID
        - concat: Concatenate all inputs into a list
        - all: Pass through all inputs as a list

    Inputs:
        Multiple inputs from different source nodes

    Outputs:
        Merged/selected result
    """

    def __init__(self):
        self._default_strategy = "first"

    @property
    def name(self) -> str:
        return "builtin.join"

    @property
    def description(self) -> str:
        return "Join multiple inputs with configurable merge strategy"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="input_A", type="any", description="First input"),
            Port(name="input_B", type="any", description="Second input"),
            Port(name="strategy", type="string", description="merge strategy: first|last|merge|concat|all"),
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="output", type="any", description="Merged output"),
            Port(name="inputs", type="list", description="All inputs as list"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: "ExecutionContext"
    ) -> Dict[str, Any]:
        strategy = inputs.get("strategy", self._default_strategy)
        input_A = inputs.get("input_A")
        input_B = inputs.get("input_B")

        # Collect all non-None inputs
        all_inputs = [inp for inp in [input_A, input_B] if inp is not None]

        if strategy == "first":
            result = input_A if input_A is not None else input_B
        elif strategy == "last":
            result = input_B if input_B is not None else input_A
        elif strategy == "merge":
            # Merge into dict with source info
            result = {
                "input_A": input_A,
                "input_B": input_B,
            }
        elif strategy == "concat":
            # Concatenate into list (works for lists and scalars)
            result = self._concat(all_inputs)
        elif strategy == "all":
            result = all_inputs
        else:
            # Default to first
            result = input_A if input_A is not None else input_B

        return {
            "output": result,
            "inputs": all_inputs,
        }

    def _concat(self, inputs: List[Any]) -> List[Any]:
        """Concatenate inputs, flattening lists where appropriate."""
        result = []
        for inp in inputs:
            if isinstance(inp, list):
                result.extend(inp)
            else:
                result.append(inp)
        return result
