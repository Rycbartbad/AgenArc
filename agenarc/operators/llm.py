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


class LLM_Task_Operator(IOperator):
    """
    LLM Task operator - execute LLM inference.

    Calls a language model API with the provided prompt and parameters.

    Inputs:
        prompt: The user prompt/message
        context: Optional context for the conversation

    Outputs:
        response: The LLM's response text
        usage: Token usage information
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
            Port(name="prompt", type="string", description="User prompt"),
            Port(name="context", type="object", description="Conversation context", default=None),
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
                api_key = os.environ.get("OPENAI_API_KEY", "")
                base_url = os.environ.get("OPENAI_BASE_URL", None)

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
            inputs: Dict with 'prompt' and optional 'context'
            context: ExecutionContext

        Returns:
            Dict with 'response' and 'usage'
        """
        prompt = inputs.get("prompt", "")
        model = context.get("_llm_model", "gpt-4")
        temperature = context.get("_llm_temperature", 0.7)
        system_prompt = context.get("_llm_system_prompt", "")

        if not prompt:
            return {
                "response": "",
                "usage": {"error": "Empty prompt"}
            }

        try:
            client = self._get_client()

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = await client.chat.completions.create(
                model=model,
                messages=messages,
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
        return "prompt" in inputs


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
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")

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
        prompt = inputs.get("prompt", "")
        system = inputs.get("system", "")
        model = context.get("_claude_model", "claude-3-sonnet-20240229")
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
