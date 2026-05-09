"""Unit tests for engine/trace.py."""

import json

import pytest

from agenarc.engine.trace import (
    NodeTrace,
    TraceCollector,
    _extract_tokens,
    _truncate_value,
)


class TestNodeTrace:
    """Tests for NodeTrace dataclass."""

    def test_node_trace_creation(self):
        """Test NodeTrace creation with all required fields."""
        trace = NodeTrace(
            node_id="node_1",
            node_type="LLM_Task",
            node_label="Chat LLM",
            start_time=1000.0,
        )
        assert trace.node_id == "node_1"
        assert trace.node_type == "LLM_Task"
        assert trace.node_label == "Chat LLM"
        assert trace.start_time == 1000.0

    def test_node_trace_defaults(self):
        """Test NodeTrace default field values."""
        trace = NodeTrace(
            node_id="node_1",
            node_type="LLM_Task",
            node_label="Chat LLM",
            start_time=1000.0,
        )
        assert trace.end_time is None
        assert trace.duration_ms is None
        assert trace.status == "pending"
        assert trace.inputs is None
        assert trace.outputs is None
        assert trace.error is None
        assert trace.tokens is None
        assert trace.children == []

    def test_node_trace_all_fields(self):
        """Test NodeTrace with all fields populated."""
        trace = NodeTrace(
            node_id="node_1",
            node_type="Router",
            node_label="Branch Router",
            start_time=1000.0,
            end_time=2000.0,
            duration_ms=1000.0,
            status="success",
            inputs={"query": "hello"},
            outputs={"response": "hi"},
            error=None,
            tokens={"prompt": 10, "completion": 20},
            children=[{"branch": "a"}],
        )
        assert trace.node_id == "node_1"
        assert trace.node_type == "Router"
        assert trace.node_label == "Branch Router"
        assert trace.start_time == 1000.0
        assert trace.end_time == 2000.0
        assert trace.duration_ms == 1000.0
        assert trace.status == "success"
        assert trace.inputs == {"query": "hello"}
        assert trace.outputs == {"response": "hi"}
        assert trace.error is None
        assert trace.tokens == {"prompt": 10, "completion": 20}
        assert trace.children == [{"branch": "a"}]


class TestTruncateValue:
    """Tests for _truncate_value helper."""

    def test_short_string_unchanged(self):
        """Test short strings are returned unchanged."""
        result = _truncate_value("hello", max_len=500)
        assert result == "hello"

    def test_long_string_truncated(self):
        """Test long strings are truncated with ellipsis."""
        long_str = "a" * 600
        result = _truncate_value(long_str, max_len=500)
        assert len(result) == 503  # 500 chars + "..."
        assert result.endswith("...")
        assert result.startswith("a" * 500)

    def test_exact_max_length_unchanged(self):
        """Test string exactly at max_len is not truncated."""
        exact_str = "b" * 500
        result = _truncate_value(exact_str, max_len=500)
        assert result == exact_str
        assert len(result) == 500

    def test_nested_dict_truncated(self):
        """Test nested dict values are truncated recursively."""
        data = {"key1": "a" * 600, "key2": {"nested": "b" * 700}}
        result = _truncate_value(data, max_len=500)
        assert result["key1"].endswith("...")
        assert len(result["key1"]) == 503
        assert result["key2"]["nested"].endswith("...")
        assert len(result["key2"]["nested"]) == 503

    def test_nested_list_truncated(self):
        """Test nested list values are truncated recursively."""
        data = ["a" * 600, ["b" * 700]]
        result = _truncate_value(data, max_len=500)
        assert result[0].endswith("...")
        assert len(result[0]) == 503
        assert result[1][0].endswith("...")
        assert len(result[1][0]) == 503

    def test_non_string_unchanged(self):
        """Test non-string values are returned unchanged."""
        data = {"int": 42, "float": 3.14, "bool": True, "none": None}
        result = _truncate_value(data, max_len=500)
        assert result == data

    def test_custom_max_len(self):
        """Test custom max_len parameter."""
        long_str = "x" * 50
        result = _truncate_value(long_str, max_len=10)
        assert len(result) == 13  # 10 chars + "..."
        assert result == "x" * 10 + "..."

    def test_empty_dict_and_list(self):
        """Test empty dict and list are returned unchanged."""
        assert _truncate_value({}) == {}
        assert _truncate_value([]) == []


class TestExtractTokens:
    """Tests for _extract_tokens helper."""

    def test_none_outputs(self):
        """Test None outputs returns None."""
        assert _extract_tokens(None) is None

    def test_non_dict_outputs(self):
        """Test non-dict outputs returns None."""
        assert _extract_tokens("string") is None
        assert _extract_tokens(42) is None
        assert _extract_tokens([1, 2, 3]) is None

    def test_missing_usage_key(self):
        """Test outputs without usage key returns None."""
        outputs = {"response": "hello"}
        assert _extract_tokens(outputs) is None

    def test_usage_not_dict(self):
        """Test usage that is not a dict returns None."""
        outputs = {"usage": "not_a_dict"}
        assert _extract_tokens(outputs) is None

    def test_extracts_both_tokens(self):
        """Test extracting prompt and completion tokens."""
        outputs = {"usage": {"prompt_tokens": 100, "completion_tokens": 50}}
        result = _extract_tokens(outputs)
        assert result == {"prompt": 100, "completion": 50}

    def test_extracts_prompt_only(self):
        """Test extracting only prompt_tokens."""
        outputs = {"usage": {"prompt_tokens": 100}}
        result = _extract_tokens(outputs)
        assert result == {"prompt": 100}

    def test_extracts_completion_only(self):
        """Test extracting only completion_tokens."""
        outputs = {"usage": {"completion_tokens": 50}}
        result = _extract_tokens(outputs)
        assert result == {"completion": 50}

    def test_empty_usage_dict(self):
        """Test empty usage dict returns None."""
        outputs = {"usage": {}}
        assert _extract_tokens(outputs) is None


class TestTraceCollector:
    """Tests for TraceCollector class."""

    @pytest.fixture
    def collector(self):
        """Create a fresh TraceCollector for each test."""
        return TraceCollector()

    @pytest.mark.asyncio
    async def test_start_execution_initializes(self, collector):
        """Test start_execution initializes trace and active lists."""
        await collector.start_execution("exec_1")
        assert collector.get_trace("exec_1") == []
        assert collector._active["exec_1"] == {}

    @pytest.mark.asyncio
    async def test_start_node_adds_active(self, collector):
        """Test start_node adds a NodeTrace to active nodes."""
        await collector.start_execution("exec_1")
        await collector.start_node(
            "exec_1",
            "node_1",
            "LLM_Task",
            "Chat",
            inputs={"query": "hello"},
        )
        active = collector._active["exec_1"]
        assert "node_1" in active
        trace = active["node_1"]
        assert trace.node_id == "node_1"
        assert trace.node_type == "LLM_Task"
        assert trace.node_label == "Chat"
        assert trace.status == "running"
        assert trace.inputs == {"query": "hello"}
        assert trace.start_time > 0

    @pytest.mark.asyncio
    async def test_start_node_truncates_inputs(self, collector):
        """Test start_node truncates long input values."""
        await collector.start_execution("exec_1")
        long_input = {"data": "x" * 1000}
        await collector.start_node(
            "exec_1",
            "node_1",
            "LLM_Task",
            "Chat",
            inputs=long_input,
        )
        trace = collector._active["exec_1"]["node_1"]
        assert trace.inputs["data"].endswith("...")
        assert len(trace.inputs["data"]) == 503

    @pytest.mark.asyncio
    async def test_end_node_moves_to_completed(self, collector):
        """Test end_node moves node from active to completed."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        await collector.end_node("exec_1", "node_1", outputs={"response": "hi"})

        assert "node_1" not in collector._active["exec_1"]
        traces = collector.get_trace("exec_1")
        assert len(traces) == 1
        assert traces[0]["node_id"] == "node_1"

    @pytest.mark.asyncio
    async def test_end_node_sets_status_success(self, collector):
        """Test end_node sets status=success on completion."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        await collector.end_node("exec_1", "node_1", outputs={"response": "hi"})

        traces = collector.get_trace("exec_1")
        assert traces[0]["status"] == "success"
        assert traces[0]["outputs"] == {"response": "hi"}

    @pytest.mark.asyncio
    async def test_end_node_calculates_duration(self, collector):
        """Test end_node calculates duration_ms correctly."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        await collector.end_node("exec_1", "node_1", outputs={})

        traces = collector.get_trace("exec_1")
        assert traces[0]["duration_ms"] > 0
        assert traces[0]["end_time"] > traces[0]["start_time"]

    @pytest.mark.asyncio
    async def test_end_node_with_error(self, collector):
        """Test end_node with error sets status=failed."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        await collector.end_node("exec_1", "node_1", error="Connection timeout")

        traces = collector.get_trace("exec_1")
        assert traces[0]["status"] == "failed"
        assert traces[0]["error"] == "Connection timeout"
        assert traces[0]["outputs"] is None

    @pytest.mark.asyncio
    async def test_end_node_explicit_tokens(self, collector):
        """Test end_node with explicit tokens parameter."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        await collector.end_node(
            "exec_1",
            "node_1",
            outputs={"response": "hi"},
            tokens={"prompt": 10, "completion": 20},
        )

        traces = collector.get_trace("exec_1")
        assert traces[0]["tokens"] == {"prompt": 10, "completion": 20}

    @pytest.mark.asyncio
    async def test_end_node_extracts_tokens_from_llm_output(self, collector):
        """Test end_node extracts tokens from LLM output usage dict."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        await collector.end_node(
            "exec_1",
            "node_1",
            outputs={
                "response": "hello",
                "usage": {"prompt_tokens": 50, "completion_tokens": 25},
            },
        )

        traces = collector.get_trace("exec_1")
        assert traces[0]["tokens"] == {"prompt": 50, "completion": 25}

    @pytest.mark.asyncio
    async def test_end_node_nonexistent_node(self, collector):
        """Test end_node for nonexistent node does nothing."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        # End a node that was never started
        await collector.end_node("exec_1", "nonexistent", outputs={})

        traces = collector.get_trace("exec_1")
        assert len(traces) == 0  # Only node_1 exists, not ended yet
        assert "node_1" in collector._active["exec_1"]

    @pytest.mark.asyncio
    async def test_end_node_truncates_outputs(self, collector):
        """Test end_node truncates long output values."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        long_output = {"data": "y" * 1000}
        await collector.end_node("exec_1", "node_1", outputs=long_output)

        traces = collector.get_trace("exec_1")
        assert traces[0]["outputs"]["data"].endswith("...")
        assert len(traces[0]["outputs"]["data"]) == 503

    @pytest.mark.asyncio
    async def test_add_children_to_router(self, collector):
        """Test add_children appends children to a Router trace."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "router_1", "Router", "Branch")
        await collector.end_node("exec_1", "router_1", outputs={"matched": "a"})
        await collector.add_children(
            "exec_1",
            "router_1",
            [{"branch": "a", "node": "node_a"}],
        )

        traces = collector.get_trace("exec_1")
        assert len(traces[0]["children"]) == 1
        assert traces[0]["children"][0] == {"branch": "a", "node": "node_a"}

    @pytest.mark.asyncio
    async def test_add_children_multiple_batches(self, collector):
        """Test add_children appends multiple batches of children."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "router_1", "Router", "Branch")
        await collector.end_node("exec_1", "router_1", outputs={})
        await collector.add_children("exec_1", "router_1", [{"branch": "a"}])
        await collector.add_children("exec_1", "router_1", [{"branch": "b"}])

        traces = collector.get_trace("exec_1")
        assert len(traces[0]["children"]) == 2

    @pytest.mark.asyncio
    async def test_add_children_nonexistent_node(self, collector):
        """Test add_children for nonexistent node does nothing."""
        await collector.start_execution("exec_1")
        # Should not raise
        await collector.add_children("exec_1", "nonexistent", [{"branch": "a"}])

    @pytest.mark.asyncio
    async def test_get_trace_returns_dicts(self, collector):
        """Test get_trace returns list of dicts."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        await collector.end_node("exec_1", "node_1", outputs={})

        traces = collector.get_trace("exec_1")
        assert isinstance(traces, list)
        assert len(traces) == 1
        assert isinstance(traces[0], dict)
        assert "node_id" in traces[0]
        assert "node_type" in traces[0]
        assert "node_label" in traces[0]
        assert "start_time" in traces[0]
        assert "end_time" in traces[0]
        assert "duration_ms" in traces[0]
        assert "status" in traces[0]
        assert "inputs" in traces[0]
        assert "outputs" in traces[0]
        assert "error" in traces[0]
        assert "tokens" in traces[0]
        assert "children" in traces[0]

    @pytest.mark.asyncio
    async def test_get_trace_empty(self, collector):
        """Test get_trace returns empty list for unknown exec_id."""
        assert collector.get_trace("nonexistent") == []

    @pytest.mark.asyncio
    async def test_get_latest_returns_most_recent(self, collector):
        """Test get_latest returns the most recent execution trace."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        await collector.end_node("exec_1", "node_1", outputs={})

        await collector.start_execution("exec_2")
        await collector.start_node("exec_2", "node_2", "Log", "Logger")
        await collector.end_node("exec_2", "node_2", outputs={})

        latest = collector.get_latest()
        assert latest is not None
        assert len(latest) == 1
        assert latest[0]["node_id"] == "node_2"

    @pytest.mark.asyncio
    async def test_get_latest_empty(self, collector):
        """Test get_latest returns None when no executions exist."""
        assert collector.get_latest() is None

    @pytest.mark.asyncio
    async def test_export_returns_valid_json(self, collector):
        """Test export returns a valid JSON string."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        await collector.end_node("exec_1", "node_1", outputs={"response": "hi"})

        exported = collector.export("exec_1")
        data = json.loads(exported)
        assert data["exec_id"] == "exec_1"
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["node_id"] == "node_1"
        assert "total_duration_ms" in data

    @pytest.mark.asyncio
    async def test_export_total_duration(self, collector):
        """Test export calculates total_duration_ms correctly."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        await collector.start_node("exec_1", "node_2", "Log", "Logger")
        await collector.end_node("exec_1", "node_1", outputs={})
        await collector.end_node("exec_1", "node_2", outputs={})

        data = json.loads(collector.export("exec_1"))
        assert len(data["nodes"]) == 2
        expected_total = data["nodes"][0]["duration_ms"] + data["nodes"][1]["duration_ms"]
        assert data["total_duration_ms"] == pytest.approx(expected_total)

    @pytest.mark.asyncio
    async def test_export_empty_execution(self, collector):
        """Test export for nonexistent exec_id returns skeleton."""
        data = json.loads(collector.export("nonexistent"))
        assert data["exec_id"] == "nonexistent"
        assert data["nodes"] == []
        assert data["total_duration_ms"] == 0

    @pytest.mark.asyncio
    async def test_clear_single_execution(self, collector):
        """Test clear removes a single execution by exec_id."""
        await collector.start_execution("exec_1")
        await collector.start_execution("exec_2")
        collector.clear("exec_1")

        assert collector.get_trace("exec_1") == []
        assert "exec_1" not in collector._active
        assert "exec_2" in collector._active

    @pytest.mark.asyncio
    async def test_clear_all_executions(self, collector):
        """Test clear with no argument removes all executions."""
        await collector.start_execution("exec_1")
        await collector.start_execution("exec_2")
        collector.clear()

        assert collector._traces == {}
        assert collector._active == {}
        assert collector.get_latest() is None

    @pytest.mark.asyncio
    async def test_clear_nonexistent_execution(self, collector):
        """Test clear with nonexistent exec_id does nothing."""
        await collector.start_execution("exec_1")
        collector.clear("nonexistent")  # Should not raise
        assert len(collector._traces) == 1

    @pytest.mark.asyncio
    async def test_concurrent_nodes_different_order(self, collector):
        """Test multiple active nodes can end in different order."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_a", "LLM_Task", "A")
        await collector.start_node("exec_1", "node_b", "Log", "B")
        await collector.start_node("exec_1", "node_c", "Router", "C")

        # End in non-start order
        await collector.end_node("exec_1", "node_c", outputs={})
        await collector.end_node("exec_1", "node_a", outputs={})
        await collector.end_node("exec_1", "node_b", outputs={})

        traces = collector.get_trace("exec_1")
        assert len(traces) == 3
        node_ids = [t["node_id"] for t in traces]
        # Should be in end order (append order)
        assert node_ids == ["node_c", "node_a", "node_b"]
        # All should be completed
        assert all(t["status"] == "success" for t in traces)

    @pytest.mark.asyncio
    async def test_concurrent_nodes_partial_completion(self, collector):
        """Test some nodes completed while others still active."""
        await collector.start_execution("exec_1")
        await collector.start_node("exec_1", "node_a", "LLM_Task", "A")
        await collector.start_node("exec_1", "node_b", "Log", "B")

        await collector.end_node("exec_1", "node_a", outputs={})

        # node_b still active
        traces = collector.get_trace("exec_1")
        assert len(traces) == 1
        assert "node_a" not in collector._active["exec_1"]
        assert "node_b" in collector._active["exec_1"]

    @pytest.mark.asyncio
    async def test_multiple_executions_independent(self, collector):
        """Test multiple executions are tracked independently."""
        await collector.start_execution("exec_a")
        await collector.start_execution("exec_b")

        await collector.start_node("exec_a", "node_1", "LLM_Task", "A")
        await collector.start_node("exec_b", "node_2", "Log", "B")

        await collector.end_node("exec_a", "node_1", outputs={})

        trace_a = collector.get_trace("exec_a")
        trace_b = collector.get_trace("exec_b")

        assert len(trace_a) == 1
        assert trace_a[0]["node_id"] == "node_1"
        assert len(trace_b) == 0  # node_2 not ended yet

    @pytest.mark.asyncio
    async def test_start_node_auto_creates_execution(self, collector):
        """Test start_node creates execution entry if not exists."""
        await collector.start_node("exec_1", "node_1", "LLM_Task", "Chat")
        assert "exec_1" in collector._active
        assert "node_1" in collector._active["exec_1"]
        # Traces list should also exist
        assert "exec_1" in collector._traces

    @pytest.mark.asyncio
    async def test_end_node_no_active(self, collector):
        """Test end_node when exec_id has no active nodes does nothing."""
        # Call end_node without any start
        await collector.end_node("exec_1", "node_1", outputs={})
        # Should not raise, and no traces
        assert collector.get_trace("exec_1") == []
