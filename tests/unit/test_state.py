"""Unit tests for engine/state.py."""

import pytest
from agenarc.engine.state import (
    StateManager,
    StateChange,
    Checkpoint,
    ExecutionContext,
)


class TestCheckpoint:
    """Tests for Checkpoint dataclass."""

    def test_checkpoint_creation(self):
        """Test Checkpoint creation."""
        checkpoint = Checkpoint(
            id="cp1",
            label="test checkpoint",
            timestamp=1000.0,
            global_state={"key": "value"},
            local_states={"node1": {"out": 42}}
        )
        assert checkpoint.id == "cp1"
        assert checkpoint.label == "test checkpoint"
        assert checkpoint.timestamp == 1000.0
        assert checkpoint.global_state == {"key": "value"}
        assert checkpoint.local_states == {"node1": {"out": 42}}


class TestStateChange:
    """Tests for StateChange dataclass."""

    def test_state_change_global(self):
        """Test StateChange for global scope."""
        change = StateChange(
            scope="global",
            key="test_key",
            old_value="old",
            new_value="new"
        )
        assert change.scope == "global"
        assert change.key == "test_key"
        assert change.old_value == "old"
        assert change.new_value == "new"

    def test_state_change_local(self):
        """Test StateChange for local scope."""
        change = StateChange(
            scope="local",
            node_id="node1",
            key="output",
            new_value=42
        )
        assert change.scope == "local"
        assert change.node_id == "node1"
        assert change.key == "output"
        assert change.new_value == 42

    def test_state_change_checkpoint(self):
        """Test StateChange for checkpoint scope."""
        change = StateChange(
            scope="checkpoint",
            checkpoint_id="cp123"
        )
        assert change.scope == "checkpoint"
        assert change.checkpoint_id == "cp123"


class TestStateManager:
    """Tests for StateManager class."""

    def test_state_manager_creation(self):
        """Test StateManager creation."""
        sm = StateManager()
        assert sm.execution_id == ""
        assert sm.graph_id == ""

    def test_initialize(self):
        """Test StateManager initialization."""
        sm = StateManager()
        sm.initialize("exec123", "graph456")

        assert sm.execution_id == "exec123"
        assert sm.graph_id == "graph456"
        assert sm.get_global("execution_id") == "exec123"
        assert sm.get_global("graph_id") == "graph456"

    def test_global_context(self):
        """Test global context get/set."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.set_global("key1", "value1")
        assert sm.get_global("key1") == "value1"

        assert sm.get_global("nonexistent") is None
        assert sm.get_global("nonexistent", "default") == "default"

    def test_global_aliases(self):
        """Test global context aliases."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.set("alias_key", "alias_value")
        assert sm.get("alias_key") == "alias_value"
        assert sm.get_global("alias_key") == "alias_value"

    def test_local_context(self):
        """Test local context get/set."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.set_local("node1", "output", 42)
        assert sm.get_local("node1", "output") == 42
        assert sm.get_local("node1", "nonexistent") is None

    def test_local_context_multiple_nodes(self):
        """Test local context for multiple nodes."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.set_local("node1", "out1", 100)
        sm.set_local("node2", "out2", 200)

        assert sm.get_local("node1", "out1") == 100
        assert sm.get_local("node2", "out2") == 200
        assert sm.get_local("node1", "out2") is None

    def test_get_node_state(self):
        """Test getting entire node state."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.set_local("node1", "a", 1)
        sm.set_local("node1", "b", 2)

        state = sm.get_node_state("node1")
        assert state == {"a": 1, "b": 2}
        # Ensure it's a copy
        state["c"] = 3
        assert sm.get_local("node1", "c") is None

    def test_set_node_state(self):
        """Test setting entire node state."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.set_node_state("node1", {"x": 10, "y": 20})
        assert sm.get_local("node1", "x") == 10
        assert sm.get_local("node1", "y") == 20

    def test_clear_node_state(self):
        """Test clearing node state."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.set_local("node1", "out", 42)
        sm.clear_node_state("node1")

        assert sm.get_node_state("node1") == {}

    def test_store_output(self):
        """Test storing node outputs."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.store_output("node1", {"response": "hello", "usage": 5})
        assert sm.get_output("node1", "response") == "hello"
        assert sm.get_output("node1", "usage") == 5

    def test_get_node_outputs(self):
        """Test getting all node outputs."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.store_output("node1", {"a": 1, "b": 2})
        outputs = sm.get_node_outputs("node1")
        assert outputs == {"a": 1, "b": 2}

    def test_checkpoint_creation(self):
        """Test checkpoint creation."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")
        sm.set_global("key", "value")
        sm.set_local("node1", "out", 42)

        cp_id = sm.checkpoint("test")
        assert cp_id is not None

        cp = sm.get_checkpoint(cp_id)
        assert cp is not None
        assert cp.label == "test"
        assert cp.global_state["key"] == "value"
        assert cp.local_states["node1"]["out"] == 42

    def test_checkpoint_restore(self):
        """Test restoring from checkpoint."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.set_global("key", "original")
        cp_id = sm.checkpoint()

        sm.set_global("key", "modified")
        assert sm.get_global("key") == "modified"

        success = sm.restore(cp_id)
        assert success is True
        assert sm.get_global("key") == "original"

    def test_checkpoint_restore_nonexistent(self):
        """Test restoring nonexistent checkpoint."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        success = sm.restore("nonexistent")
        assert success is False

    def test_list_checkpoints(self):
        """Test listing checkpoints."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        cp1 = sm.checkpoint("first")
        cp2 = sm.checkpoint("second")

        checkpoints = sm.list_checkpoints()
        assert len(checkpoints) == 2
        assert checkpoints[0].label == "first"
        assert checkpoints[1].label == "second"

    def test_get_latest_checkpoint(self):
        """Test getting latest checkpoint."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        assert sm.get_latest_checkpoint() is None

        sm.checkpoint("first")
        sm.checkpoint("second")

        latest = sm.get_latest_checkpoint()
        assert latest is not None
        assert latest.label == "second"

    def test_max_checkpoints(self):
        """Test max checkpoints limit."""
        sm = StateManager(max_checkpoints=3)
        sm.initialize("exec1", "graph1")

        for i in range(5):
            sm.checkpoint(f"cp{i}")

        checkpoints = sm.list_checkpoints()
        assert len(checkpoints) == 3
        assert checkpoints[0].label == "cp2"
        assert checkpoints[2].label == "cp4"

    def test_snapshot_and_restore(self):
        """Test snapshot and restore."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.set_global("g1", "v1")
        sm.set_local("node1", "l1", "lv1")

        snapshot = sm.snapshot()
        assert snapshot["execution_id"] == "exec1"
        assert snapshot["global"]["g1"] == "v1"
        assert snapshot["local"]["node1"]["l1"] == "lv1"

        sm.set_global("g1", "modified")
        sm.restore_snapshot(snapshot)

        assert sm.get_global("g1") == "v1"
        assert sm.get_local("node1", "l1") == "lv1"

    def test_listener(self):
        """Test state change listener."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        changes = []

        def listener(change):
            changes.append(change)

        sm.add_listener(listener)
        sm.set_global("key", "value")

        assert len(changes) == 1
        assert changes[0].scope == "global"
        assert changes[0].key == "key"

        sm.remove_listener(listener)
        sm.set_global("key2", "value2")
        assert len(changes) == 1


class TestExecutionContext:
    """Tests for ExecutionContext class."""

    def test_context_creation(self):
        """Test ExecutionContext creation."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        ctx = ExecutionContext(sm)

        assert ctx.execution_id == "exec1"
        assert ctx.graph_id == "graph1"

    def test_context_get_set(self):
        """Test context get/set."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        ctx = ExecutionContext(sm)
        ctx.set("key", "value")

        assert ctx.get("key") == "value"

    def test_context_checkpoint(self):
        """Test context checkpoint."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        ctx = ExecutionContext(sm)
        ctx.set("key", "value")

        cp_id = ctx.checkpoint("test")
        assert cp_id is not None

    def test_context_restore(self):
        """Test context restore."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        ctx = ExecutionContext(sm)
        ctx.set("key", "original")

        cp_id = ctx.checkpoint()
        ctx.set("key", "modified")

        ctx.restore(cp_id)
        assert ctx.get("key") == "original"

    def test_context_node_output(self):
        """Test context node output access."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        sm.store_output("node1", {"response": "hello"})

        ctx = ExecutionContext(sm)
        assert ctx.get_node_output("node1", "response") == "hello"
        assert ctx.get_node_outputs("node1") == {"response": "hello"}

    def test_context_snapshot(self):
        """Test context snapshot."""
        sm = StateManager()
        sm.initialize("exec1", "graph1")

        ctx = ExecutionContext(sm)
        ctx.set("key", "value")

        snapshot = ctx.snapshot()
        assert snapshot["execution_id"] == "exec1"

        ctx.restore_snapshot(snapshot)
        assert ctx.get("key") == "value"
