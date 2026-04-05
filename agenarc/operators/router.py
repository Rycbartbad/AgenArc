"""
Router Operator

Conditional branching based on condition expressions.
Supports if-else and switch-case style routing.
"""

from typing import Any, Dict, List, Optional

from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port, Condition, ConditionOperator
from agenarc.engine.state import ExecutionContext


class RouterOperator(IOperator):
    """
    Router operator - route execution based on conditions.

    Evaluates condition expressions and routes to appropriate output branch.

    Inputs:
        input: The value to evaluate conditions against

    Outputs:
        output_A: Branch A output (default)
        output_B: Branch B output

    Config:
        conditions: List[Condition] - conditions to evaluate
        default: str - default branch ("A" or "B")
    """

    @property
    def name(self) -> str:
        return "builtin.router"

    @property
    def description(self) -> str:
        return "Route execution based on condition expressions"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="input", type="any", description="Value to evaluate"),
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="output_A", type="any", description="Branch A output"),
            Port(name="output_B", type="any", description="Branch B output"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        input_value = inputs.get("input")

        # Get conditions from config
        conditions = context.get("_router_conditions", [])
        default_branch = context.get("_router_default", "A")

        # Evaluate conditions
        for condition in conditions:
            if self._evaluate_condition(condition, input_value, context):
                # Match found - route to appropriate output
                if condition.output == "A" or condition.output == "output_A":
                    return {"output_A": input_value, "output_B": None}
                else:
                    return {"output_A": None, "output_B": input_value}

        # No match - use default
        if default_branch == "A":
            return {"output_A": input_value, "output_B": None}
        else:
            return {"output_A": None, "output_B": input_value}

    def _evaluate_condition(
        self,
        condition: Condition,
        input_value: Any,
        context: ExecutionContext
    ) -> bool:
        """Evaluate a single condition."""
        # Handle compound conditions
        if condition.and_conditions:
            return all(
                self._evaluate_condition(c, input_value, context)
                for c in condition.and_conditions
            )

        if condition.or_conditions:
            return any(
                self._evaluate_condition(c, input_value, context)
                for c in condition.or_conditions
            )

        if condition.not_condition:
            return not self._evaluate_condition(
                condition.not_condition, input_value, context
            )

        # Simple condition
        ref = condition.ref or "input"
        operator = condition.operator
        expected_value = condition.value

        # Resolve the actual value to compare
        if ref == "input":
            actual_value = input_value
        elif ref.startswith("context."):
            actual_value = context.get(ref[8:], None)
        elif ref.startswith("nodes."):
            # nodes.<node_id>.outputs.<port_name>
            parts = ref.split(".")
            if len(parts) >= 4:
                node_id = parts[1]
                port_name = parts[3]
                actual_value = context.get_node_output(node_id, port_name)
            else:
                actual_value = None
        else:
            actual_value = context.get(ref, None)

        return self._compare_values(actual_value, operator, expected_value)

    def _compare_values(
        self,
        actual: Any,
        operator: ConditionOperator,
        expected: Any
    ) -> bool:
        """Compare actual value with expected using operator."""
        if operator == ConditionOperator.EQ:
            return actual == expected
        elif operator == ConditionOperator.NE:
            return actual != expected
        elif operator == ConditionOperator.GT:
            return actual > expected
        elif operator == ConditionOperator.GTE:
            return actual >= expected
        elif operator == ConditionOperator.LT:
            return actual < expected
        elif operator == ConditionOperator.LTE:
            return actual <= expected
        elif operator == ConditionOperator.CONTAINS:
            if isinstance(actual, str):
                return expected in actual
            elif isinstance(actual, (list, tuple)):
                return expected in actual
            elif isinstance(actual, dict):
                return expected in actual.values()
            return False
        elif operator == ConditionOperator.STARTS_WITH:
            if isinstance(actual, str):
                return actual.startswith(expected)
            return False
        elif operator == ConditionOperator.ENDS_WITH:
            if isinstance(actual, str):
                return actual.endswith(expected)
            return False
        elif operator == ConditionOperator.IN:
            return actual in expected if expected else False
        elif operator == ConditionOperator.NOT_IN:
            return actual not in expected if expected else True
        elif operator == ConditionOperator.EXISTS:
            return actual is not None
        elif operator == ConditionOperator.NOT_EXISTS:
            return actual is None

        return False


# Registry reference
def get_operator():
    return RouterOperator()
