"""
Loop Control Operator

Loop control for iteration over collections with accumulation.
Supports max iterations and termination conditions.
"""

from typing import Any, Dict, List, Optional

from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port, Condition, ConditionOperator
from agenarc.engine.state import ExecutionContext


class Loop_Control_Operator(IOperator):
    """
    Loop Control operator - iterate over collections.

    Supports:
    - Iterating over arrays/lists
    - Max iteration limits
    - Accumulator pattern
    - Termination conditions

    Inputs:
        iterate_on: Collection to iterate over
        max_iterations: Maximum number of iterations (default 100)

    Outputs:
        iteration_count: Current iteration number
        current_item: Current item from collection
        accumulator: Accumulated value across iterations
        done: Whether iteration is complete
    """

    @property
    def name(self) -> str:
        return "builtin.loop_control"

    @property
    def description(self) -> str:
        return "Iterate over collections with accumulation"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="iterate_on", type="array", description="Collection to iterate"),
            Port(name="max_iterations", type="integer", description="Max iterations", default=100),
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="iteration_count", type="integer", description="Current iteration"),
            Port(name="current_item", type="any", description="Current item"),
            Port(name="accumulator", type="any", description="Accumulated value"),
            Port(name="done", type="boolean", description="Iteration complete"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        collection = inputs.get("iterate_on", [])
        max_iterations = inputs.get("max_iterations", 100)

        # Get loop state
        loop_id = context.get("_loop_id", "default")
        iteration = context.get(f"_loop_{loop_id}_iteration", 0)
        accumulator = context.get(f"_loop_{loop_id}_accumulator", None)

        # Get termination conditions
        termination_conditions = context.get("_loop_termination_conditions", [])
        checkpoint_enabled = context.get("_loop_checkpoint", False)

        # Check if collection is valid
        if not isinstance(collection, (list, tuple)):
            return {
                "iteration_count": iteration,
                "current_item": None,
                "accumulator": accumulator,
                "done": True,
            }

        # Check max iterations
        if iteration >= max_iterations:
            return {
                "iteration_count": iteration,
                "current_item": None,
                "accumulator": accumulator,
                "done": True,
            }

        # Check if iteration complete
        if iteration >= len(collection):
            return {
                "iteration_count": iteration,
                "current_item": None,
                "accumulator": accumulator,
                "done": True,
            }

        # Get current item
        current_item = collection[iteration]

        # Check termination conditions
        for condition in termination_conditions:
            if self._evaluate_condition(condition, current_item, context):
                # Termination condition met
                return {
                    "iteration_count": iteration,
                    "current_item": current_item,
                    "accumulator": accumulator,
                    "done": True,
                }

        # Create checkpoint if enabled
        if checkpoint_enabled:
            checkpoint_id = context.checkpoint(f"loop_pre_{loop_id}_{iteration}")
            context.set(f"_loop_{loop_id}_checkpoint", checkpoint_id)

        # Update loop state
        context.set(f"_loop_{loop_id}_iteration", iteration + 1)
        context.set(f"_loop_{loop_id}_current_item", current_item)

        return {
            "iteration_count": iteration,
            "current_item": current_item,
            "accumulator": accumulator,
            "done": False,
        }

    def _evaluate_condition(
        self,
        condition: Condition,
        current_item: Any,
        context: ExecutionContext
    ) -> bool:
        """Evaluate a termination condition."""
        from agenarc.operators.router import RouterOperator

        router = RouterOperator()
        return router._evaluate_condition(condition, current_item, context)


# Registry reference
def get_operator():
    return Loop_Control_Operator()
