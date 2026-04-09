"""
Join Operator for AgenArc

Provides synchronization for multiple parallel branches.
"""

from typing import Any, Dict, List

from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port


class JoinOperator(IOperator):
    """
    Join Operator - synchronizes multiple parallel branches.

    Reads inputs from context based on edges pointing to this node.
    Waits for all incoming edges to complete, then merges their outputs.

    Config:
        strategy: merge strategy
            - first: Return the first input
            - last: Return the last input
            - merge: Merge all inputs into a dict
            - concat: Concatenate all inputs into a list

    Note:
        Join does not declare fixed input ports.
        It reads from context based on edge sourcePort values:
        - For edge (source=A, targetPort=input), reads context["nodes.A.<sourcePort>"]
    """

    def __init__(self):
        self._default_strategy = "merge"

    @property
    def name(self) -> str:
        return "builtin.join"

    @property
    def description(self) -> str:
        return "Join multiple branches with configurable merge strategy"

    def get_input_ports(self) -> List[Port]:
        # Join does not declare fixed input ports
        return []

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="output", type="any", description="Merged output"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: "ExecutionContext"
    ) -> Dict[str, Any]:
        strategy = context.get("_join_strategy", self._default_strategy)
        node_id = context.get("_node_id", "join")

        # Collect all inputs from context based on edges
        # Edge format: source --sourcePort--> join
        # Context key: nodes.{source}.{sourcePort}
        collected_inputs = {}

        # Get edge information from context
        incoming_edges = context.get("_incoming_edges", [])

        for edge in incoming_edges:
            source = edge.get("source")
            source_port = edge.get("sourcePort", "")
            if source and source_port:
                key = f"nodes.{source}.{source_port}"
                value = context.get(key)
                if value is not None:
                    collected_inputs[f"{source}.{source_port}"] = value

        # Merge based on strategy
        if strategy == "first":
            result = next(iter(collected_inputs.values()), None) if collected_inputs else None
        elif strategy == "last":
            result = list(collected_inputs.values())[-1] if collected_inputs else None
        elif strategy == "merge":
            result = collected_inputs
        elif strategy == "concat":
            result = []
            for v in collected_inputs.values():
                if isinstance(v, list):
                    result.extend(v)
                else:
                    result.append(v)
        else:
            # Default to merge
            result = collected_inputs

        return {"output": result}
