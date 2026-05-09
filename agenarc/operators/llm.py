"""
LLM Operators

LLM Task operator for calling language model APIs.
Supports OpenAI-compatible APIs with streaming and provider fallback.
"""

from collections.abc import AsyncIterator
from typing import Any

from agenarc.engine.state import ExecutionContext
from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port


def _get_llm_config():
    """Lazy import config to avoid circular dependency."""
    from agenarc.config import get_config
    return get_config()


def _normalize_error(exc: Exception) -> dict[str, Any]:
    """Convert exception to structured error dict with type classification."""
    exc_str = str(exc)
    exc_type = type(exc).__name__.lower()

    # Classify error type and retryability
    if "api_key" in exc_str.lower() or "auth" in exc_str.lower():
        error_type = "auth_error"
        retryable = False
    elif "rate limit" in exc_str.lower() or "429" in exc_str:
        error_type = "rate_limit"
        retryable = True
    elif "timeout" in exc_str.lower() or "timed out" in exc_str.lower():
        error_type = "timeout"
        retryable = True
    elif "connection" in exc_str.lower() or "network" in exc_str.lower():
        error_type = "connection_error"
        retryable = True
    elif "import" in exc_type or "modulenotfound" in exc_type:
        error_type = "import_error"
        retryable = False
    else:
        error_type = "api_error"
        retryable = True

    return {
        "type": error_type,
        "message": exc_str,
        "retryable": retryable,
    }


class LLM_Task_Operator(IOperator):
    """
    LLM Task operator - execute LLM inference.

    Calls a language model API with the provided messages list and parameters.
    Supports streaming responses and provider fallback.

    Inputs:
        messages: List of conversation messages [{"role": "user", "content": "..."}]
        system_prompt: System prompt (passed via config, not messages)

    Outputs:
        response: The LLM's response text
        usage: Token usage information
        error: Structured error info (if failed)

    Config:
        model: Model name (e.g., "deepseek-chat")
        temperature: Temperature parameter
        system_prompt: System prompt for the conversation
        stream: Enable streaming responses (default: false)
        providers: List of providers for fallback (default: ["openai", "deepseek"])
    """

    def __init__(self):
        self._clients: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "builtin.llm_task"

    @property
    def description(self) -> str:
        return "Execute LLM inference task"

    @property
    def version(self) -> str:
        return "1.1.0"

    def get_input_ports(self) -> list[Port]:
        return [
            Port(name="messages", type="array", description="Conversation messages list", default=[]),
        ]

    def get_output_ports(self) -> list[Port]:
        return [
            Port(name="response", type="string", description="LLM response"),
            Port(name="usage", type="object", description="Token usage info"),
            Port(name="error", type="object", description="Error info if request failed"),
        ]

    def _get_client(self, provider: str = None, base_url: str = None, api_key: str = None):
        """Get or create the LLM client."""
        try:
            from openai import AsyncOpenAI
            config = _get_llm_config()

            # Use provided values or fall back to config
            if not base_url:
                if provider:
                    provider_config = config.get_provider_config(provider)
                    base_url = provider_config.get("base_url")
                    api_key = api_key or provider_config.get("api_key")
                else:
                    base_url = config.get_openai_base_url()
                    api_key = config.get_openai_api_key()

            api_key = api_key or ""

            # Create client with the specified or default configuration
            client_key = f"{base_url}:{api_key[:8] if api_key else ''}"
            if client_key not in self._clients:
                self._clients[client_key] = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                )

            return self._clients[client_key]
        except ImportError:
            raise ImportError(
                "OpenAI library not installed. "
                "Install with: pip install openai"
            )

    def _get_provider_order(self, node_config: dict[str, Any]) -> list[str]:
        """Get ordered list of providers to try (node config overrides global)."""
        # Explicit providers list in node config
        if "providers" in node_config:
            return node_config["providers"]

        # Single provider in node config
        if "provider" in node_config:
            return [node_config["provider"]]

        # Default provider order from config
        _get_llm_config()
        return ["openai", "deepseek"]

    async def _stream_response(self, client, model: str, messages: list[dict], temperature: float) -> AsyncIterator[str]:
        """Yield response chunks via streaming."""
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def execute(
        self,
        inputs: dict[str, Any],
        context: ExecutionContext
    ) -> dict[str, Any]:
        """
        Execute LLM inference with streaming and provider fallback.

        Args:
            inputs: Dict with 'messages' list
            context: ExecutionContext

        Returns:
            Dict with 'response', 'usage', and optionally 'error'
        """
        config = _get_llm_config()
        messages = inputs.get("messages", [])

        # Get node config for provider/model override
        node_config = context.get("_node_config", {})

        # Streaming mode
        stream_enabled = node_config.get("stream", False)

        # Get provider order for fallback
        providers = self._get_provider_order(node_config)
        model = node_config.get("model")
        temperature = node_config.get("temperature") or config.get_openai_temperature()
        system_prompt = node_config.get("system_prompt", "")

        if not messages:
            return {
                "response": "",
                "error": {"type": "validation_error", "message": "Empty messages list", "retryable": False}
            }

        # Build API messages: system prompt + conversation history
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        # Try providers in order
        last_error = None
        for provider in providers:
            try:
                provider_config = config.get_provider_config(provider)
                if not provider_config:
                    continue

                base_url = provider_config.get("base_url")
                api_key = provider_config.get("api_key", "")
                if not model:
                    model = provider_config.get("default_model")

                if not model:
                    continue

                client = self._get_client(provider=provider, base_url=base_url, api_key=api_key)

                if stream_enabled:
                    # Streaming: collect all chunks into single response
                    chunks = []
                    async for chunk in self._stream_response(client, model, api_messages, temperature):
                        chunks.append(chunk)

                    full_response = "".join(chunks)
                    return {
                        "response": full_response,
                        "usage": {"streaming": True, "provider": provider},
                    }
                else:
                    # Non-streaming: single API call
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
                        "provider": provider,
                    }

                    return {
                        "response": content,
                        "usage": usage,
                    }

            except Exception as e:
                last_error = e
                # Try next provider
                continue

        # All providers failed
        error_info = _normalize_error(last_error) if last_error else {
            "type": "unknown_error",
            "message": "All providers failed",
            "retryable": False,
        }

        return {
            "response": "",
            "error": error_info,
        }

    async def validate(self, inputs: dict[str, Any]) -> bool:
        """Validate inputs before execution."""
        return "messages" in inputs

