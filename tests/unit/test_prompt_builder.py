"""Unit tests for Prompt_Builder operator."""

import pytest
from agenarc.operators.builtin import Prompt_Builder_Operator
from agenarc.engine.state import StateManager, ExecutionContext


def create_context():
    """Create a test execution context."""
    sm = StateManager()
    sm.initialize("test_exec", "test_graph")
    return ExecutionContext(sm)


class TestPromptBuilderOperator:
    """Tests for Prompt_Builder_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Prompt_Builder_Operator()
        assert op.name == "builtin.prompt_builder"

    def test_description(self):
        """Test operator description."""
        op = Prompt_Builder_Operator()
        assert op.description == "Build and manage conversation message history"

    def test_input_ports(self):
        """Test operator input ports."""
        op = Prompt_Builder_Operator()
        ports = op.get_input_ports()
        assert len(ports) == 2
        port_names = {p.name for p in ports}
        assert "user" in port_names
        assert "assistant" in port_names

    def test_output_ports(self):
        """Test operator output ports."""
        op = Prompt_Builder_Operator()
        ports = op.get_output_ports()
        assert len(ports) == 1
        port_names = {p.name for p in ports}
        assert "messages" in port_names

    @pytest.mark.asyncio
    async def test_first_message_user(self):
        """Test first message can be user."""
        op = Prompt_Builder_Operator()
        ctx = create_context()
        ctx.set("_node_id", "pb_1")

        result = await op.execute({"user": "Hello!"}, ctx)

        assert result["messages"] == [
            {"role": "user", "content": "Hello!"}
        ]

    @pytest.mark.asyncio
    async def test_first_message_assistant(self):
        """Test first message can be assistant."""
        op = Prompt_Builder_Operator()
        ctx = create_context()
        ctx.set("_node_id", "pb_1")

        result = await op.execute({"assistant": "Hi, how can I help?"}, ctx)

        assert result["messages"] == [
            {"role": "assistant", "content": "Hi, how can I help?"}
        ]

    @pytest.mark.asyncio
    async def test_alternating_user_assistant(self):
        """Test alternating user and assistant messages."""
        op = Prompt_Builder_Operator()
        ctx = create_context()
        ctx.set("_node_id", "pb_1")

        # First: user
        await op.execute({"user": "Hello!"}, ctx)
        # Second: assistant
        result1 = await op.execute({"assistant": "Hi!"}, ctx)
        # Third: user
        result2 = await op.execute({"user": "How are you?"}, ctx)

        assert result2["messages"] == [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "How are you?"},
        ]

    @pytest.mark.asyncio
    async def test_violation_user_after_user(self):
        """Test error when user follows user."""
        op = Prompt_Builder_Operator()
        ctx = create_context()
        ctx.set("_node_id", "pb_1")

        # First: user
        await op.execute({"user": "Hello!"}, ctx)
        # Second: user (violation!)
        result = await op.execute({"user": "Again!"}, ctx)

        assert "error" in result
        assert "alternation violation" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_violation_assistant_after_assistant(self):
        """Test error when assistant follows assistant."""
        op = Prompt_Builder_Operator()
        ctx = create_context()
        ctx.set("_node_id", "pb_1")

        # First: assistant
        await op.execute({"assistant": "Hi!"}, ctx)
        # Second: assistant (violation!)
        result = await op.execute({"assistant": "Again!"}, ctx)

        assert "error" in result
        assert "alternation violation" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_max_history(self):
        """Test max_history limits messages."""
        op = Prompt_Builder_Operator()
        ctx = create_context()
        ctx.set("_node_id", "pb_1")
        ctx.set("_node_config", {"max_history": 3})

        # Add more than max_history messages
        await op.execute({"user": "1"}, ctx)
        await op.execute({"assistant": "2"}, ctx)
        await op.execute({"user": "3"}, ctx)
        await op.execute({"assistant": "4"}, ctx)
        result = await op.execute({"user": "5"}, ctx)

        # Should keep only last 3
        messages = result["messages"]
        assert len(messages) == 3
        # First message should be "3" (user), not "1"
        assert messages[0]["content"] == "3"
        assert messages[2]["content"] == "5"

    @pytest.mark.asyncio
    async def test_no_message_provided(self):
        """Test when neither user nor assistant provided."""
        op = Prompt_Builder_Operator()
        ctx = create_context()
        ctx.set("_node_id", "pb_1")

        result = await op.execute({}, ctx)

        # Should return empty messages (no error for first empty call)
        assert result["messages"] == []

    @pytest.mark.asyncio
    async def test_context_key_isolation(self):
        """Test different nodes have isolated message lists."""
        op1 = Prompt_Builder_Operator()
        op2 = Prompt_Builder_Operator()
        ctx = create_context()
        ctx.set("_node_id", "pb_1")

        # Add message to pb_1
        await op1.execute({"user": "Hello from pb_1"}, ctx)

        # pb_2 should have empty messages
        ctx.set("_node_id", "pb_2")
        result = await op2.execute({"user": "Hello from pb_2"}, ctx)

        # pb_2's messages should only have its own message
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "Hello from pb_2"