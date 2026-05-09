"""
Prompt Builder Operator

Manages conversation message history with alternating role enforcement.
"""

from typing import Any

from agenarc.engine.state import ExecutionContext
from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port


class Prompt_Builder_Operator(IOperator):
    """
    Prompt Builder operator - manages conversation message history.

    Maintains a messages list in context, appending user/assistant messages
    with safety checks to ensure alternating roles.

    Inputs:
        user: User message to append (mutually exclusive with assistant)
        assistant: Assistant message to append (mutually exclusive with user)

    Outputs:
        messages: The complete messages list

    Config:
        history: Custom history key name (default: node ID)
        max_history: Maximum number of messages to keep (default: 100)
    """

    def __init__(self):
        self._history_key = None

    @property
    def name(self) -> str:
        return "builtin.prompt_builder"

    @property
    def description(self) -> str:
        return "Build and manage conversation message history"

    def get_input_ports(self) -> list[Port]:
        return [
            Port(name="user", type="string", description="User message", default=None),
            Port(name="assistant", type="string", description="Assistant message", default=None),
        ]

    def get_output_ports(self) -> list[Port]:
        return [
            Port(name="messages", type="array", description="Conversation messages list"),
        ]

    async def execute(
        self,
        inputs: dict[str, Any],
        context: ExecutionContext
    ) -> dict[str, Any]:
        user_msg = inputs.get("user")
        assistant_msg = inputs.get("assistant")

        # Get node config
        node_config = context.get("_node_config", {})
        max_history = node_config.get("max_history", 100)

        # Get node ID for context key
        node_id = context.get("_node_id", "prompt_builder")

        # Determine history key from config or default to node ID
        if self._history_key is None:
            history_name = node_config.get("history", node_id)
            self._history_key = history_name

        # Get existing messages from context
        messages = context.get(self._history_key, [])

        # Safety check: ensure alternating roles
        if messages:
            last_role = messages[-1].get("role")
            if last_role == "user" and user_msg is not None:
                return {"messages": messages, "error": "Cannot add user message after user (alternation violation)"}
            if last_role == "assistant" and assistant_msg is not None:
                return {"messages": messages, "error": "Cannot add assistant message after assistant (alternation violation)"}

        # Append the appropriate message
        if user_msg is not None:
            messages.append({"role": "user", "content": user_msg})
        elif assistant_msg is not None:
            messages.append({"role": "assistant", "content": assistant_msg})

        # Trim to max_history (keep oldest messages)
        if len(messages) > max_history:
            messages = messages[-max_history:]

        # Store back to context
        context.set(self._history_key, messages)

        return {"messages": messages}
