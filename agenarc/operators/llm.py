"""
LLM Operators

LLM Task operator for calling language model APIs.
Supports OpenAI-compatible APIs.
"""

import os
from typing import Any, Dict, List, Optional

from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port
from agenarc.engine.state import ExecutionContext


def _get_llm_config():
    """Lazy import config to avoid circular dependency."""
    from agenarc.config import get_config
    return get_config()


class LLM_Task_Operator(IOperator):
    """
    LLM Task operator - execute LLM inference.

    Calls a language model API with the provided messages list and parameters.

    Inputs:
        messages: List of conversation messages [{"role": "user", "content": "..."}]
        system_prompt: System prompt (passed via config, not messages)

    Outputs:
        response: The LLM's response text
        usage: Token usage information

    Config:
        model: Model name (e.g., "deepseek-chat")
        temperature: Temperature parameter
        system_prompt: System prompt for the conversation
    """

    def __init__(self):
        self._client = None

    @property
    def name(self) -> str:
        return "builtin.llm_task"

    @property
    def description(self) -> str:
        return "Execute LLM inference task"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="messages", type="array", description="Conversation messages list", default=[]),
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="response", type="string", description="LLM response"),
            Port(name="usage", type="object", description="Token usage info"),
        ]

    def _get_client(self):
        """Get or create the LLM client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                config = _get_llm_config()

                api_key = config.get_openai_api_key() or ""
                base_url = config.get_openai_base_url()

                self._client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                )
            except ImportError:
                raise ImportError(
                    "OpenAI library not installed. "
                    "Install with: pip install openai"
                )

        return self._client

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Execute LLM inference.

        Args:
            inputs: Dict with 'messages' list
            context: ExecutionContext

        Returns:
            Dict with 'response' and 'usage'
        """
        config = _get_llm_config()
        messages = inputs.get("messages", [])
        model = context.get("_llm_model") or config.get_openai_model()
        temperature = context.get("_llm_temperature") or config.get_openai_temperature()

        # Get system_prompt from config
        node_config = context.get("_node_config", {})
        system_prompt = node_config.get("system_prompt", "")

        if not messages:
            return {
                "response": "",
                "usage": {"error": "Empty messages"}
            }

        try:
            client = self._get_client()

            # Build API messages: system prompt + conversation history
            api_messages = []
            if system_prompt:
                api_messages.append({"role": "system", "content": system_prompt})

            # Extend with the conversation messages
            api_messages.extend(messages)

            response = await client.chat.completions.create(
                model=model,
                messages=api_messages,
                temperature=temperature,
            )

            content = response.choices[0].message.content if response.choices else ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }

            return {
                "response": content,
                "usage": usage,
            }

        except Exception as e:
            return {
                "response": f"Error: {str(e)}",
                "usage": {"error": str(e)}
            }

    async def validate(self, inputs: Dict[str, Any]) -> bool:
        """Validate inputs before execution."""
        return "messages" in inputs


class Anthropic_Task_Operator(IOperator):
    """
    Anthropic Claude Task operator.

    Alternative LLM operator using Anthropic's Claude API.
    """

    def __init__(self):
        self._client = None

    @property
    def name(self) -> str:
        return "anthropic.claude_complete"

    @property
    def description(self) -> str:
        return "Execute Anthropic Claude inference"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="prompt", type="string", description="User prompt"),
            Port(name="system", type="string", description="System prompt", default=""),
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="response", type="string", description="Claude response"),
            Port(name="usage", type="object", description="Token usage info"),
        ]

    def _get_client(self):
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                config = _get_llm_config()
                api_key = config.get_anthropic_api_key() or ""

                self._client = AsyncAnthropic(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "Anthropic library not installed. "
                    "Install with: pip install anthropic"
                )

        return self._client

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Execute Claude inference."""
        config = _get_llm_config()
        prompt = inputs.get("prompt", "")
        system = inputs.get("system", "")
        model = context.get("_claude_model") or config.get_anthropic_model()
        temperature = context.get("_claude_temperature", 0.7)
        max_tokens = context.get("_claude_max_tokens", 4096)

        if not prompt:
            return {"response": "", "usage": {"error": "Empty prompt"}}

        try:
            client = self._get_client()

            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )

            return {
                "response": response.content[0].text if response.content else "",
                "usage": {
                    "input_tokens": response.usage.input_tokens if hasattr(response.usage, 'input_tokens') else 0,
                    "output_tokens": response.usage.output_tokens if hasattr(response.usage, 'output_tokens') else 0,
                }
            }

        except Exception as e:
            return {
                "response": f"Error: {str(e)}",
                "usage": {"error": str(e)}
            }
