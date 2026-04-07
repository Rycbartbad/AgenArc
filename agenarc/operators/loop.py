"""
Loop Control Operator

Loop control for iteration over collections with accumulation.
Supports feedback loops: outputs done=False to continue, done=True to exit.
"""

from typing import Any, Dict, List, Optional

from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port, Condition
from agenarc.engine.state import ExecutionContext


class Loop_Control_Operator(IOperator):
    """
    Loop Control operator - iterate over collections with feedback support.

    This operator implements a feedback loop pattern:
    - On iteration start: outputs current_item, iteration_count, done=False
    - After body executes and accumulator is updated, next iteration begins
    - When collection exhausted or max_iterations reached: done=True

    Inputs:
        iterate_on: Collection to iterate over (array)
        max_iterations: Maximum number of iterations (default 100)
        accumulator_input: Value to add to accumulator (from previous body node)

    Outputs:
        iteration_count: Current iteration number (0-indexed)
        current_item: Current item from collection
        accumulator: Accumulated value across iterations
        done: Whether iteration is complete (False = continue loop)

    Usage in feedback loop:
        1. Loop_Control outputs current_item, done=False
        2. Body nodes execute, potentially updating accumulator
        3. Body output feeds back to Loop_Control (accumulator_input)
        4. Loop_Control reads accumulator, advances iteration
        5. When done=True, loop exits
    """

    @property
    def name(self) -> str:
        return "builtin.loop_control"

    @property
    def description(self) -> str:
        return "Iterate over collections with feedback loop support"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="iterate_on", type="array", description="Collection to iterate"),
            Port(name="max_iterations", type="integer", description="Max iterations", default=100),
            Port(name="accumulator_input", type="any", description="Input to accumulator from body"),
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="iteration_count", type="integer", description="Current iteration (0-indexed)"),
            Port(name="current_item", type="any", description="Current item"),
            Port(name="accumulator", type="any", description="Accumulated value"),
            Port(name="done", type="boolean", description="False=continue loop, True=exit"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        # Get collection
        collection = inputs.get("iterate_on", [])
        max_iterations = inputs.get("max_iterations", 100)
        accumulator_input = inputs.get("accumulator_input")

        # Get loop state from context
        loop_id = context.get("_loop_id", "default")
        iteration = context.get(f"_loop_{loop_id}_iteration", 0)
        accumulator = context.get(f"_loop_{loop_id}_accumulator", None)

        # Validate collection
        if not isinstance(collection, (list, tuple)):
            return {
                "iteration_count": iteration,
                "current_item": None,
                "accumulator": accumulator,
                "done": True,
            }

        # Check termination conditions
        if iteration >= max_iterations:
            return self._make_output(iteration, None, accumulator, True, loop_id, context)

        if iteration >= len(collection):
            return self._make_output(iteration, None, accumulator, True, loop_id, context)

        # Get current item
        current_item = collection[iteration]

        # Update accumulator with input from body
        if accumulator_input is not None:
            if accumulator is None:
                accumulator = accumulator_input
            elif isinstance(accumulator, list):
                accumulator.append(accumulator_input)
            elif isinstance(accumulator, dict):
                accumulator.update(accumulator_input)
            else:
                # For scalar accumulator, replace or extend based on config
                accumulator = accumulator_input

        # Advance iteration for next time
        next_iteration = iteration + 1

        # Save state to context for next iteration
        context.set(f"_loop_{loop_id}_iteration", next_iteration)
        context.set(f"_loop_{loop_id}_accumulator", accumulator)
        context.set(f"_loop_{loop_id}_current_item", current_item)

        return {
            "iteration_count": iteration,
            "current_item": current_item,
            "accumulator": accumulator,
            "done": False,  # Continue loop
        }

    def _make_output(
        self,
        iteration: int,
        current_item: Any,
        accumulator: Any,
        done: bool,
        loop_id: str,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Create output and update context."""
        context.set(f"_loop_{loop_id}_iteration", iteration)
        context.set(f"_loop_{loop_id}_accumulator", accumulator)
        return {
            "iteration_count": iteration,
            "current_item": current_item,
            "accumulator": accumulator,
            "done": done,
        }


# Registry reference
def get_operator():
    return Loop_Control_Operator()