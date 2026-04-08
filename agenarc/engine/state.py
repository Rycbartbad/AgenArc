"""
State Management

Hierarchical state management for AgenArc execution:
- Global Context (shared across all nodes)
- Local State (per-node state)
- Checkpoints (for interruption and recovery)
"""

import asyncio
import copy
import json
import time
import uuid
import warnings
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class Checkpoint:
    """Represents a point-in-time snapshot of execution state."""
    id: str
    label: str
    timestamp: float
    global_state: Dict[str, Any]
    local_states: Dict[str, Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    """
    Manages checkpoint persistence to disk.

    Provides:
    - File-based checkpoint storage
    - Automatic checkpoint cleanup
    - Checkpoint recovery on restart

    Checkpoints are stored as JSON files in:
        ~/.agenarc/checkpoints/<execution_id>/<checkpoint_id>.json
    """

    def __init__(
        self,
        checkpoint_dir: Optional[Path] = None,
        max_checkpoints: int = 100
    ):
        """
        Initialize CheckpointManager.

        Args:
            checkpoint_dir: Directory for checkpoint files
            max_checkpoints: Maximum checkpoints to keep per execution
        """
        if checkpoint_dir is None:
            checkpoint_dir = Path.home() / ".agenarc" / "checkpoints"

        self._checkpoint_dir = checkpoint_dir
        self._max_checkpoints = max_checkpoints
        self._checkpoints: OrderedDict[str, Checkpoint] = OrderedDict()

        # Ensure directory exists
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

    @property
    def checkpoint_dir(self) -> Path:
        """Get checkpoint directory path."""
        return self._checkpoint_dir

    def save_checkpoint(self, checkpoint: Checkpoint) -> str:
        """
        Save checkpoint to disk and memory.

        Args:
            checkpoint: Checkpoint to save

        Returns:
            Checkpoint ID
        """
        # Save to memory
        self._checkpoints[checkpoint.id] = checkpoint

        # Enforce max checkpoints
        while len(self._checkpoints) > self._max_checkpoints:
            oldest = self._checkpoints.popitem(last=False)
            self._delete_checkpoint_file(oldest[1].id, checkpoint.metadata.get("execution_id", "default"))

        # Save to disk
        self._save_to_disk(checkpoint)

        return checkpoint.id

    def load_checkpoint(self, checkpoint_id: str, execution_id: str) -> Optional[Checkpoint]:
        """
        Load checkpoint from disk or memory.

        Args:
            checkpoint_id: Checkpoint ID
            execution_id: Execution ID

        Returns:
            Checkpoint or None if not found
        """
        # Check memory first
        if checkpoint_id in self._checkpoints:
            return self._checkpoints[checkpoint_id]

        # Try to load from disk
        return self._load_from_disk(checkpoint_id, execution_id)

    def list_checkpoints(self, execution_id: str) -> List[Checkpoint]:
        """
        List all checkpoints for an execution.

        Args:
            execution_id: Execution ID

        Returns:
            List of checkpoints
        """
        checkpoints = []

        # Load from disk
        exec_dir = self._checkpoint_dir / execution_id
        if exec_dir.exists():
            for file_path in exec_dir.glob("*.json"):
                checkpoint = self._read_checkpoint_file(file_path)
                if checkpoint:
                    checkpoints.append(checkpoint)

        # Add memory checkpoints
        for checkpoint in self._checkpoints.values():
            if checkpoint.metadata.get("execution_id") == execution_id:
                if checkpoint not in checkpoints:
                    checkpoints.append(checkpoint)

        # Sort by timestamp
        checkpoints.sort(key=lambda c: c.timestamp)
        return checkpoints

    def delete_checkpoint(self, checkpoint_id: str, execution_id: str) -> bool:
        """
        Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID
            execution_id: Execution ID

        Returns:
            True if deleted
        """
        # Remove from memory
        if checkpoint_id in self._checkpoints:
            del self._checkpoints[checkpoint_id]

        # Remove from disk
        return self._delete_checkpoint_file(checkpoint_id, execution_id)

    def delete_all_checkpoints(self, execution_id: str) -> None:
        """Delete all checkpoints for an execution."""
        # Clear memory
        to_remove = [
            cid for cid, cp in self._checkpoints.items()
            if cp.metadata.get("execution_id") == execution_id
        ]
        for cid in to_remove:
            del self._checkpoints[cid]

        # Clear disk
        exec_dir = self._checkpoint_dir / execution_id
        if exec_dir.exists():
            for file_path in exec_dir.glob("*.json"):
                file_path.unlink()
            exec_dir.rmdir()

    def _get_checkpoint_path(self, checkpoint_id: str, execution_id: str) -> Path:
        """Get file path for checkpoint."""
        exec_dir = self._checkpoint_dir / execution_id
        return exec_dir / f"{checkpoint_id}.json"

    def _save_to_disk(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to disk."""
        execution_id = checkpoint.metadata.get("execution_id", "default")
        file_path = self._get_checkpoint_path(checkpoint.id, execution_id)

        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize checkpoint
        data = {
            "id": checkpoint.id,
            "label": checkpoint.label,
            "timestamp": checkpoint.timestamp,
            "global_state": checkpoint.global_state,
            "local_states": checkpoint.local_states,
            "metadata": checkpoint.metadata,
        }

        # Write atomically
        tmp_path = file_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)
        tmp_path.replace(file_path)

    def _load_from_disk(self, checkpoint_id: str, execution_id: str) -> Optional[Checkpoint]:
        """Load checkpoint from disk."""
        file_path = self._get_checkpoint_path(checkpoint_id, execution_id)

        if not file_path.exists():
            return None

        return self._read_checkpoint_file(file_path)

    def _read_checkpoint_file(self, file_path: Path) -> Optional[Checkpoint]:
        """Read checkpoint from file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return Checkpoint(
                id=data["id"],
                label=data["label"],
                timestamp=data["timestamp"],
                global_state=data["global_state"],
                local_states=data["local_states"],
                metadata=data.get("metadata", {}),
            )
        except Exception:
            return None

    def _delete_checkpoint_file(self, checkpoint_id: str, execution_id: str) -> bool:
        """Delete checkpoint file."""
        file_path = self._get_checkpoint_path(checkpoint_id, execution_id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False


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
        auto_checkpoint: bool = False,
        large_object_keys: List[str] = None,
        strict_mode: bool = False
    ):
        self._max_checkpoints = max_checkpoints
        self._auto_checkpoint = auto_checkpoint

        # Copy-on-write configuration
        self._large_object_keys: Set[str] = set(large_object_keys or [])
        self._strict_mode = strict_mode

        # Global context (shared across all nodes)
        self._global: Dict[str, Any] = {}

        # Per-node local states
        self._local: Dict[str, Dict[str, Any]] = {}

        # Transactional memory storage
        self._transactional_pending: Dict[str, Any] = {}
        self._transactional_enabled: bool = False

        # Checkpoints
        self._checkpoints: OrderedDict[str, Checkpoint] = OrderedDict()

        # State change listeners
        self._listeners: List[Callable[[StateChange], None]] = []

        # Object ID tracking for in-place mutation detection
        self._origin_ids: Dict[str, int] = {}

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

    # ========== Transactional Memory ==========

    def enable_transaction(self) -> None:
        """Enable transactional mode for Memory_I/O operations."""
        self._transactional_enabled = True
        self._transactional_pending = {}

    def get_transactional(self, key: str, default: Any = None) -> Any:
        """Get value, checking pending transactional writes first."""
        if key in self._transactional_pending:
            return self._transactional_pending[key]
        return self._global.get(key, default)

    def set_transactional(self, key: str, value: Any) -> None:
        """Set value in transactional pending (not committed yet)."""
        self._transactional_pending[key] = value

    def commit_transaction(self) -> None:
        """Commit all pending transactional writes to global state."""
        for key, value in self._transactional_pending.items():
            if value is None:
                # None means delete
                if key in self._global:
                    del self._global[key]
            else:
                self._global[key] = value
        self._transactional_pending = {}
        self._transactional_enabled = False

    def rollback_transaction(self) -> None:
        """Rollback all pending transactional writes."""
        self._transactional_pending = {}
        self._transactional_enabled = False

    @property
    def in_transaction(self) -> bool:
        """Check if transaction is in progress."""
        return self._transactional_enabled

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

        Each output port value is stored directly in context with key:
        nodes.{node_id}.{port_name} = value

        This allows downstream nodes to read outputs via edge sourcePort.

        Args:
            node_id: Node ID
            outputs: Output dictionary from node execution
        """
        if node_id not in self._local:
            self._local[node_id] = {}

        # Store full outputs dict for backward compatibility
        self._local[node_id]["_outputs"] = outputs
        self._global[f"nodes.{node_id}.outputs"] = outputs

        # Store each output port directly with key = nodes.{node_id}.{port_name}
        for port_name, value in outputs.items():
            self._global[f"nodes.{node_id}.{port_name}"] = value

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

    Provides a clean interface to the StateManager with Copy-on-Write support
    for large objects and in-place mutation detection in strict mode.
    """

    def __init__(self, state_manager: StateManager):
        self._state = state_manager
        self._cache: Dict[str, Any] = {}  # CoW cache for large objects

    @property
    def execution_id(self) -> str:
        return self._state.execution_id

    @property
    def graph_id(self) -> str:
        return self._state.graph_id

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from global context with CoW support.

        For large_object_keys: returns a cached deep copy (CoW)
        For strict_mode: tracks object ID for mutation detection
        """
        value = self._state.get_global(key, default)

        if value is None:
            return default

        # Large object keys use Copy-on-Write
        if key in self._state._large_object_keys:
            if key not in self._cache:
                self._cache[key] = copy.deepcopy(value)
            return self._cache[key]

        # Track object ID for in-place mutation detection in strict mode
        if self._state._strict_mode and key not in self._cache:
            self._state._origin_ids[key] = id(value)

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set value in global context.

        Always stores a deep copy to prevent external modification.
        """
        if key in self._state._large_object_keys:
            # Large object: invalidate cache and store deep copy
            self._cache[key] = copy.deepcopy(value)
            self._state.set_global(key, self._cache[key])
        else:
            # Normal object: store deep copy
            self._state.set_global(key, copy.deepcopy(value))

        # Update origin ID tracking in strict mode
        if self._state._strict_mode:
            self._state._origin_ids[key] = id(self._state.get_global(key))

    def post_node_execute(self, node_id: str) -> None:
        """
        Check for in-place mutations after node execution.

        Called by the executor after each node completes.
        Detects if a non-large_object key's value was mutated in-place
        (e.g., list.append(), dict['key'] = value) without going through set().
        """
        if not self._state._strict_mode:
            return

        for key in self._state._origin_ids:
            if key in self._state._large_object_keys:
                continue  # Large objects use CoW, no mutation risk
            current = self._state.get_global(key)
            if current is None:
                continue
            current_id = id(current)
            original_id = self._state._origin_ids[key]
            if current_id != original_id:
                warnings.warn(
                    f"Node '{node_id}' performed in-place mutation on '{key}' "
                    f"without declaring it as large_object. This can cause "
                    f"data races in PARALLEL mode. Declare it in "
                    f"manifest.json context.large_object_keys or use "
                    f"context.set() instead of direct mutation.",
                    RuntimeWarning
                )
                # Update tracking to avoid repeated warnings
                self._state._origin_ids[key] = current_id

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
