"""
Execution Tracing Engine

Provides NodeTrace dataclass and TraceCollector for recording
node-level execution traces with timing, status, and token usage.
"""

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NodeTrace:
    """Trace record for a single node execution."""

    node_id: str
    node_type: str
    node_label: str
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    status: str = "pending"
    inputs: dict | None = None
    outputs: dict | None = None
    error: str | None = None
    tokens: dict | None = None
    children: list[dict] = field(default_factory=list)


def _truncate_value(value: Any, max_len: int = 500) -> Any:
    """Recursively truncate string values longer than max_len."""
    if isinstance(value, str):
        return value[:max_len] + "..." if len(value) > max_len else value
    if isinstance(value, dict):
        return {k: _truncate_value(v, max_len) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate_value(item, max_len) for item in value]
    return value


def _extract_tokens(outputs: dict | None) -> dict | None:
    """Extract token usage from LLM node outputs."""
    if not outputs or not isinstance(outputs, dict):
        return None
    usage = outputs.get("usage")
    if not usage or not isinstance(usage, dict):
        return None
    tokens = {}
    if "prompt_tokens" in usage:
        tokens["prompt"] = usage["prompt_tokens"]
    if "completion_tokens" in usage:
        tokens["completion"] = usage["completion_tokens"]
    return tokens if tokens else None


class TraceCollector:
    """
    Collects and manages execution traces for graph node execution.

    Thread-safe via asyncio.Lock. Each execution is keyed by exec_id.
    """

    def __init__(self) -> None:
        self._traces: dict[str, list[NodeTrace]] = {}
        self._active: dict[str, dict[str, NodeTrace]] = {}
        self._lock = asyncio.Lock()

    async def start_execution(self, exec_id: str) -> None:
        """Begin tracking a new execution."""
        async with self._lock:
            self._traces[exec_id] = []
            self._active[exec_id] = {}

    async def start_node(
        self,
        exec_id: str,
        node_id: str,
        node_type: str,
        label: str,
        inputs: dict | None = None,
    ) -> None:
        """Record the start of a node execution."""
        trace = NodeTrace(
            node_id=node_id,
            node_type=node_type,
            node_label=label,
            start_time=time.time(),
            status="running",
            inputs=_truncate_value(inputs) if inputs else None,
        )
        async with self._lock:
            if exec_id not in self._active:
                self._active[exec_id] = {}
            self._active[exec_id][node_id] = trace
            if exec_id not in self._traces:
                self._traces[exec_id] = []

    async def end_node(
        self,
        exec_id: str,
        node_id: str,
        outputs: dict | None = None,
        error: str | None = None,
        tokens: dict | None = None,
    ) -> None:
        """Record the completion of a node execution."""
        async with self._lock:
            active_nodes = self._active.get(exec_id, {})
            trace = active_nodes.pop(node_id, None)
            if trace is None:
                return

            now = time.time()
            trace.end_time = now
            trace.duration_ms = (now - trace.start_time) * 1000

            if error:
                trace.status = "failed"
                trace.error = error
            else:
                trace.status = "success"
                trace.outputs = _truncate_value(outputs) if outputs else None
                trace.tokens = tokens or _extract_tokens(outputs)

            self._traces[exec_id].append(trace)

    async def add_children(self, exec_id: str, node_id: str, children: list[dict]) -> None:
        """Add child branch info to a completed Router node trace."""
        async with self._lock:
            traces = self._traces.get(exec_id, [])
            # Search in reverse to find the most recent trace for this node
            for trace in reversed(traces):
                if trace.node_id == node_id:
                    trace.children.extend(children)
                    break

    def get_trace(self, exec_id: str) -> list[dict]:
        """Get the full trace for an execution as a list of dicts."""
        traces = self._traces.get(exec_id, [])
        return [asdict(t) for t in traces]

    def get_latest(self) -> list[dict] | None:
        """Get the trace for the most recent execution."""
        if not self._traces:
            return None
        latest_id = list(self._traces.keys())[-1]
        return self.get_trace(latest_id)

    def export(self, exec_id: str) -> str:
        """Export execution trace as a JSON string."""
        traces = self._traces.get(exec_id, [])
        total_duration = sum((t.duration_ms or 0) for t in traces)
        data = {
            "exec_id": exec_id,
            "nodes": [asdict(t) for t in traces],
            "total_duration_ms": total_duration,
        }
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)

    def list_executions(self) -> list[str]:
        """Return list of all available execution IDs."""
        return list(self._traces.keys())

    def clear(self, exec_id: str | None = None) -> None:
        """Clear traces. If exec_id is None, clear all."""
        if exec_id:
            self._traces.pop(exec_id, None)
            self._active.pop(exec_id, None)
        else:
            self._traces.clear()
            self._active.clear()
