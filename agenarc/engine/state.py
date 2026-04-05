"""
State Management

Hierarchical state management for AgenArc execution:
- Global Context (shared across all nodes)
- Local State (per-node state)
- Checkpoints (for interruption and recovery)
"""

import asyncio
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Checkpoint:
    """Represents a point-in-time snapshot of execution state."""
    id: str
    label: str
    timestamp: float
    global_state: Dict[str, Any]
    local_states: Dict[str, Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateChange:
    """Represents a state change event."""
    scope: str  # "global", "local", "checkpoint", "restore"
    node_id: Optional[str] = None
    key: Optional[str] = None
    old_value: Any = None
    new_value: Any = None
    checkpoint_id: Optional[str] = None


class StateManager:
    """
    Manages execution state with support for:
    - Hierarchical state (global context + local state)
    - Checkpointing for long-running tasks
    - Interrupt and resume capability

    Architecture:
        Global Context (shared across all nodes)
        ├── execution_id, graph_id
        ├── cross-node shared variables
        └── checkpoint history

        Local State (per-node)
        ├── node-specific variables
        ├── input/output values
        └── retry counters

        Checkpoints
        ├── full state snapshot
        └── used for recovery
    """

    def __init__(
        self,
        max_checkpoints: int = 100,
        auto_checkpoint: bool = False
    ):
        self._max_checkpoints = max_checkpoints
        self._auto_checkpoint = auto_checkpoint

        # Global context (shared across all nodes)
        self._global: Dict[str, Any] = {}

        # Per-node local states
        self._local: Dict[str, Dict[str, Any]] = {}

        # Checkpoints
        self._checkpoints: OrderedDict[str, Checkpoint] = OrderedDict()

        # State change listeners
        self._listeners: List[Callable[[StateChange], None]] = []

        # Execution metadata
        self._execution_id: str = ""
        self._graph_id: str = ""

    # ========== Execution Metadata ==========

    def initialize(self, execution_id: str, graph_id: str) -> None:
        """Initialize state manager with execution metadata."""
        self._execution_id = execution_id
        self._graph_id = graph_id
        self._global = {
            "execution_id": execution_id,
            "graph_id": graph_id,
        }

    @property
    def execution_id(self) -> str:
        return self._execution_id

    @property
    def graph_id(self) -> str:
        return self._graph_id

    # ========== Global Context ==========

    def get_global(self, key: str, default: Any = None) -> Any:
        """
        Get value from global context.

        Args:
            key: Variable name
            default: Default value if not found

        Returns:
            Value or default
        """
        return self._global.get(key, default)

    def set_global(self, key: str, value: Any) -> None:
        """
        Set value in global context.

        Args:
            key: Variable name
            value: Value to set
        """
        old_value = self._global.get(key)
        self._global[key] = value
        self._notify(StateChange(
            scope="global",
            key=key,
            old_value=old_value,
            new_value=value
        ))

    def get(self, key: str, default: Any = None) -> Any:
        """Alias for get_global."""
        return self.get_global(key, default)

    def set(self, key: str, value: Any) -> None:
        """Alias for set_global."""
        self.set_global(key, value)

    # ========== Local State ==========

    def get_local(
        self,
        node_id: str,
        key: str,
        default: Any = None
    ) -> Any:
        """
        Get value from node's local state.

        Args:
            node_id: Node ID
            key: Variable name
            default: Default value if not found

        Returns:
            Value or default
        """
        node_state = self._local.get(node_id, {})
        return node_state.get(key, default)

    def set_local(
        self,
        node_id: str,
        key: str,
        value: Any
    ) -> None:
        """
        Set value in node's local state.

        Args:
            node_id: Node ID
            key: Variable name
            value: Value to set
        """
        if node_id not in self._local:
            self._local[node_id] = {}

        old_value = self._local[node_id].get(key)
        self._local[node_id][key] = value

        self._notify(StateChange(
            scope="local",
            node_id=node_id,
            key=key,
            old_value=old_value,
            new_value=value
        ))

    def get_node_state(self, node_id: str) -> Dict[str, Any]:
        """
        Get entire local state for a node.

        Args:
            node_id: Node ID

        Returns:
            Copy of node's local state
        """
        return self._local.get(node_id, {}).copy()

    def set_node_state(
        self,
        node_id: str,
        state: Dict[str, Any]
    ) -> None:
        """
        Set entire local state for a node.

        Args:
            node_id: Node ID
            state: State dictionary
        """
        self._local[node_id] = state.copy()
        self._notify(StateChange(
            scope="local",
            node_id=node_id,
            key="*",
            new_value=state
        ))

    def clear_node_state(self, node_id: str) -> None:
        """
        Clear all state for a node.

        Args:
            node_id: Node ID
        """
        if node_id in self._local:
            old_state = self._local[node_id].copy()
            del self._local[node_id]
            self._notify(StateChange(
                scope="local",
                node_id=node_id,
                key="*",
                old_value=old_state,
                new_value=None
            ))

    # ========== Node Output Storage ==========

    def store_output(
        self,
        node_id: str,
        outputs: Dict[str, Any]
    ) -> None:
        """
        Store node outputs for downstream consumption.

        Args:
            node_id: Node ID
            outputs: Output dictionary from node execution
        """
        if node_id not in self._local:
            self._local[node_id] = {}

        self._local[node_id]["_outputs"] = outputs

        # Also store at global level for easy access
        self._global[f"nodes.{node_id}.outputs"] = outputs

    def get_output(self, node_id: str, port_name: str) -> Any:
        """
        Get output from a specific node port.

        Args:
            node_id: Node ID
            port_name: Output port name

        Returns:
            Output value or None
        """
        outputs = self._local.get(node_id, {}).get("_outputs", {})
        return outputs.get(port_name)

    def get_node_outputs(self, node_id: str) -> Dict[str, Any]:
        """
        Get all outputs from a node.

        Args:
            node_id: Node ID

        Returns:
            All node outputs
        """
        return self._local.get(node_id, {}).get("_outputs", {})

    # ========== Checkpointing ==========

    def checkpoint(self, label: str = None) -> str:
        """
        Create a checkpoint of current state.

        Args:
            label: Optional label for this checkpoint

        Returns:
            Checkpoint ID for later restoration
        """
        checkpoint_id = str(uuid.uuid4())

        checkpoint = Checkpoint(
            id=checkpoint_id,
            label=label or f"checkpoint_{len(self._checkpoints)}",
            timestamp=time.time(),
            global_state=self._global.copy(),
            local_states={
                node_id: state.copy()
                for node_id, state in self._local.items()
            }
        )

        self._checkpoints[checkpoint_id] = checkpoint

        # Enforce max checkpoints (FIFO eviction)
        while len(self._checkpoints) > self._max_checkpoints:
            self._checkpoints.popitem(last=False)

        self._notify(StateChange(
            scope="checkpoint",
            checkpoint_id=checkpoint_id
        ))

        return checkpoint_id

    def restore(self, checkpoint_id: str) -> bool:
        """
        Restore state from checkpoint.

        Args:
            checkpoint_id: Checkpoint ID to restore

        Returns:
            True if successful, False if checkpoint not found
        """
        checkpoint = self._checkpoints.get(checkpoint_id)

        if not checkpoint:
            return False

        # Restore global state
        self._global = checkpoint.global_state.copy()

        # Restore local states
        self._local = {
            node_id: state.copy()
            for node_id, state in checkpoint.local_states.items()
        }

        self._notify(StateChange(
            scope="restore",
            checkpoint_id=checkpoint_id
        ))

        return True

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """
        Get checkpoint metadata without restoring.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            Checkpoint object or None
        """
        return self._checkpoints.get(checkpoint_id)

    def list_checkpoints(self) -> List[Checkpoint]:
        """
        List all checkpoints.

        Returns:
            List of checkpoints in creation order
        """
        return list(self._checkpoints.values())

    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """
        Get the most recent checkpoint.

        Returns:
            Latest checkpoint or None
        """
        if not self._checkpoints:
            return None
        return list(self._checkpoints.values())[-1]

    # ========== Snapshot & Restore ==========

    def snapshot(self) -> Dict[str, Any]:
        """
        Create a snapshot of entire state.

        Returns:
            Snapshot dictionary
        """
        return {
            "execution_id": self._execution_id,
            "graph_id": self._graph_id,
            "global": self._global.copy(),
            "local": {
                node_id: state.copy()
                for node_id, state in self._local.items()
            },
            "checkpoint_ids": list(self._checkpoints.keys())
        }

    def restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        Restore state from snapshot.

        Args:
            snapshot: Snapshot dictionary from snapshot()
        """
        self._execution_id = snapshot.get("execution_id", "")
        self._graph_id = snapshot.get("graph_id", "")
        self._global = snapshot.get("global", {}).copy()
        self._local = {
            node_id: state.copy()
            for node_id, state in snapshot.get("local", {}).items()
        }

    # ========== Listeners ==========

    def add_listener(self, listener: Callable[[StateChange], None]) -> None:
        """
        Add state change listener.

        Args:
            listener: Callback function
        """
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[StateChange], None]) -> None:
        """
        Remove state change listener.

        Args:
            listener: Callback function to remove
        """
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, change: StateChange) -> None:
        """Notify all listeners of state change."""
        for listener in self._listeners:
            try:
                listener(change)
            except Exception as e:
                import logging
                logging.error(f"State listener error: {e}")

    # ========== Context Access ==========

    def get_context(self) -> "ExecutionContext":
        """
        Get ExecutionContext for operator execution.

        Returns:
            ExecutionContext object
        """
        return ExecutionContext(self)


class ExecutionContext:
    """
    Context object passed to operators during execution.

    Provides a clean interface to the StateManager.
    """

    def __init__(self, state_manager: StateManager):
        self._state = state_manager

    @property
    def execution_id(self) -> str:
        return self._state.execution_id

    @property
    def graph_id(self) -> str:
        return self._state.graph_id

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from global context."""
        return self._state.get_global(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in global context."""
        self._state.set_global(key, value)

    def get_node_output(self, node_id: str, port_name: str) -> Any:
        """Get output from a specific node port."""
        return self._state.get_output(node_id, port_name)

    def get_node_outputs(self, node_id: str) -> Dict[str, Any]:
        """Get all outputs from a node."""
        return self._state.get_node_outputs(node_id)

    def checkpoint(self, label: str = None) -> str:
        """Create a checkpoint."""
        return self._state.checkpoint(label)

    def restore(self, checkpoint_id: str) -> bool:
        """Restore from checkpoint."""
        return self._state.restore(checkpoint_id)

    def snapshot(self) -> Dict[str, Any]:
        """Create a full state snapshot."""
        return self._state.snapshot()

    def restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Restore from snapshot."""
        self._state.restore_snapshot(snapshot)
