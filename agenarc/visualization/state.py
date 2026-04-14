"""
Graph State Tracker for Visualization

Tracks graph execution state including:
- Node execution statuses
- Node outputs
- Context snapshots
- Execution timeline
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeStatus(str, Enum):
    """Node execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TimelineEvent:
    """An event in the execution timeline."""
    timestamp: str
    event_type: str
    node_id: Optional[str]
    data: Dict[str, Any]


@dataclass
class GraphExecutionState:
    """Complete graph execution state."""
    execution_id: str
    status: str  # idle, running, paused, completed, failed
    node_statuses: Dict[str, NodeStatus]
    current_node_id: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    timeline: List[TimelineEvent] = field(default_factory=list)


class GraphStateTracker:
    """
    Tracks graph execution state for visualization.

    Maintains:
    - Node execution statuses
    - Node outputs
    - Context snapshots
    - Execution timeline
    """

    def __init__(self):
        self._execution_id: Optional[str] = None
        self._status: str = "idle"
        self._node_statuses: Dict[str, NodeStatus] = {}
        self._node_outputs: Dict[str, Dict[str, Any]] = {}
        self._context_snapshot: Dict[str, Any] = {}
        self._current_node_id: Optional[str] = None
        self._start_time: Optional[str] = None
        self._end_time: Optional[str] = None
        self._timeline: List[TimelineEvent] = []

    def reset(self) -> None:
        """Reset all tracked state."""
        self._execution_id = None
        self._status = "idle"
        self._node_statuses = {}
        self._node_outputs = {}
        self._context_snapshot = {}
        self._current_node_id = None
        self._start_time = None
        self._end_time = None
        self._timeline = []

    def start_execution(self, execution_id: str) -> None:
        """Mark execution as started."""
        self._execution_id = execution_id
        self._status = "running"
        self._start_time = datetime.now().isoformat()
        self._add_timeline_event("execution:start", None, {"executionId": execution_id})

    def end_execution(self, status: str) -> None:
        """Mark execution as ended."""
        self._status = status
        self._end_time = datetime.now().isoformat()
        self._add_timeline_event("execution:end", None, {
            "executionId": self._execution_id,
            "status": status
        })

    def update_node_status(
        self,
        node_id: str,
        status: NodeStatus
    ) -> None:
        """Update node execution status."""
        self._node_statuses[node_id] = status
        if status == NodeStatus.RUNNING:
            self._current_node_id = node_id
        self._add_timeline_event(f"node:{status.value}", node_id, {
            "nodeId": node_id,
            "status": status.value
        })

    def record_node_output(
        self,
        node_id: str,
        outputs: Dict[str, Any]
    ) -> None:
        """Record node outputs."""
        self._node_outputs[node_id] = outputs

    def capture_context_snapshot(
        self,
        global_context: Dict[str, Any],
        local_context: Dict[str, Dict[str, Any]]
    ) -> None:
        """Capture current context state."""
        self._context_snapshot = {
            "global": global_context,
            "local": local_context,
            "timestamp": datetime.now().isoformat()
        }

    def get_current_state(self) -> GraphExecutionState:
        """Get complete current execution state."""
        return GraphExecutionState(
            execution_id=self._execution_id or "",
            status=self._status,
            node_statuses=self._node_statuses.copy(),
            current_node_id=self._current_node_id,
            start_time=self._start_time,
            end_time=self._end_time,
            timeline=self._timeline.copy()
        )

    def get_node_status(self, node_id: str) -> NodeStatus:
        """Get status for a specific node."""
        return self._node_statuses.get(node_id, NodeStatus.PENDING)

    def get_node_outputs(self, node_id: str) -> Dict[str, Any]:
        """Get outputs for a specific node."""
        return self._node_outputs.get(node_id, {})

    def get_context_snapshot(self) -> Dict[str, Any]:
        """Get current context snapshot."""
        return self._context_snapshot.copy()

    def _add_timeline_event(
        self,
        event_type: str,
        node_id: Optional[str],
        data: Dict[str, Any]
    ) -> None:
        """Add an event to the timeline."""
        self._timeline.append(TimelineEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            node_id=node_id,
            data=data
        ))
