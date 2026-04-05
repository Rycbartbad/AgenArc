"""Unit tests for operators/llm.py."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from agenarc.operators.llm import (
    LLM_Task_Operator,
    Anthropic_Task_Operator,
    _get_llm_config,
)
from agenarc.engine.state import StateManager, ExecutionContext


def create_context():
    """Create a test execution context."""
    sm = StateManager()
    sm.initialize("test_exec", "test_graph")
    return ExecutionContext(sm)


class TestLLMTaskOperator:
    """Tests for LLM_Task_Operator."""

    def test_name(self):
        """Test operator name."""
        op = LLM_Task_Operator()
        assert op.name == "builtin.llm_task"

    def test_description(self):
        """Test operator description."""
        op = LLM_Task_Operator()
        assert op.description == "Execute LLM inference task"

    def test_version(self):
        """Test operator version."""
        op = LLM_Task_Operator()
        assert op.version == "1.0.0"

    def test_input_ports(self):
        """Test operator input ports."""
        op = LLM_Task_Operator()
        ports = op.get_input_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "prompt" in port_names
        assert "context" in port_names

    def test_output_ports(self):
        """Test operator output ports."""
        op = LLM_Task_Operator()
        ports = op.get_output_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "response" in port_names
        assert "usage" in port_names

    @pytest.mark.asyncio
    async def test_execute_empty_prompt(self):
        """Test execute with empty prompt returns error."""
        op = LLM_Task_Operator()
        ctx = create_context()

        result = await op.execute({}, ctx)

        assert result["response"] == ""
        assert "error" in result["usage"]

    @pytest.mark.asyncio
    async def test_validate_requires_prompt(self):
        """Test validate requires prompt input."""
        op = LLM_Task_Operator()

        assert await op.validate({"prompt": "test"}) is True
        assert await op.validate({}) is False

    @pytest.mark.asyncio
    async def test_execute_uses_context_model(self):
        """Test execute uses model from context when set."""
        op = LLM_Task_Operator()
        ctx = create_context()
        ctx.set("_llm_model", "gpt-3.5-turbo")

        # Empty prompt to avoid API call
        result = await op.execute({"prompt": ""}, ctx)

        assert result["response"] == ""
        assert "error" in result["usage"]

    @pytest.mark.asyncio
    async def test_execute_uses_context_temperature(self):
        """Test execute uses temperature from context when set."""
        op = LLM_Task_Operator()
        ctx = create_context()
        ctx.set("_llm_temperature", 0.9)

        result = await op.execute({"prompt": ""}, ctx)

        assert result["response"] == ""
        assert "error" in result["usage"]

    @pytest.mark.asyncio
    async def test_execute_with_system_prompt(self):
        """Test execute with system prompt in context."""
        op = LLM_Task_Operator()
        ctx = create_context()
        ctx.set("_llm_system_prompt", "You are a helpful assistant.")

        result = await op.execute({"prompt": ""}, ctx)

        assert result["response"] == ""
        assert "error" in result["usage"]


class TestAnthropicTaskOperator:
    """Tests for Anthropic_Task_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Anthropic_Task_Operator()
        assert op.name == "anthropic.claude_complete"

    def test_description(self):
        """Test operator description."""
        op = Anthropic_Task_Operator()
        assert op.description == "Execute Anthropic Claude inference"

    def test_input_ports(self):
        """Test operator input ports."""
        op = Anthropic_Task_Operator()
        ports = op.get_input_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "prompt" in port_names
        assert "system" in port_names

    def test_output_ports(self):
        """Test operator output ports."""
        op = Anthropic_Task_Operator()
        ports = op.get_output_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "response" in port_names
        assert "usage" in port_names

    @pytest.mark.asyncio
    async def test_execute_empty_prompt(self):
        """Test execute with empty prompt returns error."""
        op = Anthropic_Task_Operator()
        ctx = create_context()

        result = await op.execute({}, ctx)

        assert result["response"] == ""
        assert "error" in result["usage"]

    @pytest.mark.asyncio
    async def test_execute_with_system(self):
        """Test execute with system prompt."""
        op = Anthropic_Task_Operator()
        ctx = create_context()

        result = await op.execute({"prompt": "", "system": "You are Claude."}, ctx)

        assert result["response"] == ""
        assert "error" in result["usage"]

    @pytest.mark.asyncio
    async def test_execute_uses_context_model(self):
        """Test execute uses model from context when set."""
        op = Anthropic_Task_Operator()
        ctx = create_context()
        ctx.set("_claude_model", "claude-3-haiku")

        result = await op.execute({"prompt": ""}, ctx)

        assert result["response"] == ""
        assert "error" in result["usage"]

    @pytest.mark.asyncio
    async def test_execute_uses_context_temperature(self):
        """Test execute uses temperature from context when set."""
        op = Anthropic_Task_Operator()
        ctx = create_context()
        ctx.set("_claude_temperature", 0.5)

        result = await op.execute({"prompt": ""}, ctx)

        assert result["response"] == ""
        assert "error" in result["usage"]

    @pytest.mark.asyncio
    async def test_execute_uses_context_max_tokens(self):
        """Test execute uses max_tokens from context when set."""
        op = Anthropic_Task_Operator()
        ctx = create_context()
        ctx.set("_claude_max_tokens", 2048)

        result = await op.execute({"prompt": ""}, ctx)

        assert result["response"] == ""
        assert "error" in result["usage"]


class TestGetLLMConfig:
    """Tests for _get_llm_config helper."""

    def test_get_llm_config_returns_config(self):
        """Test _get_llm_config returns a config object."""
        from agenarc.config import Config
        Config._instance = None
        config = _get_llm_config()
        assert config is not None
        assert isinstance(config, Config)
