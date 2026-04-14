"""
Execution Events for Visualization

Emits events when nodes execute, complete, or fail.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ExecutionEvent(str, Enum):
    """Event types for execution visualization."""
    NODE_START = "node:start"
    NODE_COMPLETE = "node:complete"
    NODE_ERROR = "node:error"
    NODE_SKIP = "node:skip"
    EXECUTION_START = "execution:start"
    EXECUTION_END = "execution:end"
    CONTEXT_UPDATE = "context:update"
    CHECKPOINT_SAVE = "checkpoint:save"


class ExecutionEventEmitter:
    """
    Emits execution events for visualization.

    Attaches to ExecutionEngine to emit WebSocket events when:
    - Node status changes (pending → running → complete/failed)
    - Context is updated
    - Checkpoint is created
    """

    def __init__(self):
        self._listeners: List[Callable[[ExecutionEvent, Dict[str, Any]], None]] = []

    def add_listener(
        self,
        callback: Callable[[ExecutionEvent, Dict[str, Any]], None]
    ) -> None:
        """Add an event listener."""
        self._listeners.append(callback)

    def remove_listener(
        self,
        callback: Callable[[ExecutionEvent, Dict[str, Any]], None]
    ) -> None:
        """Remove an event listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def emit(
        self,
        event_type: ExecutionEvent,
        data: Dict[str, Any]
    ) -> None:
        """Emit event to all listeners."""
        for listener in self._listeners:
            try:
                listener(event_type, data)
            except Exception:
                pass  # Don't let listener errors break emission

    def emit_node_start(
        self,
        node_id: str,
        execution_id: str
    ) -> None:
        """Emit node start event."""
        self.emit(ExecutionEvent.NODE_START, {
            "nodeId": node_id,
            "executionId": execution_id,
        })

    def emit_node_complete(
        self,
        node_id: str,
        execution_id: str,
        outputs: Dict[str, Any]
    ) -> None:
        """Emit node complete event."""
        self.emit(ExecutionEvent.NODE_COMPLETE, {
            "nodeId": node_id,
            "executionId": execution_id,
            "outputs": outputs,
        })

    def emit_node_error(
        self,
        node_id: str,
        execution_id: str,
        error: str
    ) -> None:
        """Emit node error event."""
        self.emit(ExecutionEvent.NODE_ERROR, {
            "nodeId": node_id,
            "executionId": execution_id,
            "error": error,
        })

    def emit_node_skip(
        self,
        node_id: str,
        execution_id: str
    ) -> None:
        """Emit node skip event."""
        self.emit(ExecutionEvent.NODE_SKIP, {
            "nodeId": node_id,
            "executionId": execution_id,
        })

    def emit_execution_start(
        self,
        execution_id: str
    ) -> None:
        """Emit execution start event."""
        self.emit(ExecutionEvent.EXECUTION_START, {
            "executionId": execution_id,
        })

    def emit_execution_end(
        self,
        execution_id: str,
        status: str
    ) -> None:
        """Emit execution end event."""
        self.emit(ExecutionEvent.EXECUTION_END, {
            "executionId": execution_id,
            "status": status,
        })

    def emit_context_update(
        self,
        context: Dict[str, Any]
    ) -> None:
        """Emit context update event."""
        self.emit(ExecutionEvent.CONTEXT_UPDATE, {
            "context": context,
        })

    def emit_checkpoint_save(
        self,
        checkpoint_id: str
    ) -> None:
        """Emit checkpoint save event."""
        self.emit(ExecutionEvent.CHECKPOINT_SAVE, {
            "checkpointId": checkpoint_id,
        })
