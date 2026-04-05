"""Unit tests for engine/state.py CheckpointManager."""

import pytest
import time
from pathlib import Path
from agenarc.engine.state import CheckpointManager, Checkpoint


class TestCheckpointManager:
    """Tests for CheckpointManager."""

    def test_checkpoint_manager_creation(self, tmp_path):
        """Test CheckpointManager can be created."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)
        assert manager is not None
        assert manager.checkpoint_dir == tmp_path

    def test_checkpoint_manager_default_dir(self):
        """Test CheckpointManager with default directory."""
        manager = CheckpointManager()
        assert manager.checkpoint_dir == Path.home() / ".agenarc" / "checkpoints"

    def test_save_checkpoint(self, tmp_path):
        """Test saving a checkpoint."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)

        checkpoint = Checkpoint(
            id="test-1",
            label="test checkpoint",
            timestamp=time.time(),
            global_state={"key": "value"},
            local_states={"node1": {"output": "result"}},
            metadata={"execution_id": "exec-1"}
        )

        checkpoint_id = manager.save_checkpoint(checkpoint)
        assert checkpoint_id == "test-1"

    def test_load_checkpoint_from_memory(self, tmp_path):
        """Test loading checkpoint from memory."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)

        checkpoint = Checkpoint(
            id="test-1",
            label="test checkpoint",
            timestamp=time.time(),
            global_state={"key": "value"},
            local_states={"node1": {}},
            metadata={"execution_id": "exec-1"}
        )

        manager.save_checkpoint(checkpoint)
        loaded = manager.load_checkpoint("test-1", "exec-1")

        assert loaded is not None
        assert loaded.id == "test-1"
        assert loaded.global_state["key"] == "value"

    def test_load_checkpoint_from_disk(self, tmp_path):
        """Test loading checkpoint from disk."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)

        checkpoint = Checkpoint(
            id="test-1",
            label="test checkpoint",
            timestamp=time.time(),
            global_state={"key": "value"},
            local_states={"node1": {}},
            metadata={"execution_id": "exec-1"}
        )

        manager.save_checkpoint(checkpoint)

        # Create new manager instance (simulates restart)
        manager2 = CheckpointManager(checkpoint_dir=tmp_path)
        loaded = manager2.load_checkpoint("test-1", "exec-1")

        assert loaded is not None
        assert loaded.id == "test-1"

    def test_load_nonexistent_checkpoint(self, tmp_path):
        """Test loading non-existent checkpoint returns None."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)

        loaded = manager.load_checkpoint("nonexistent", "exec-1")
        assert loaded is None

    def test_list_checkpoints(self, tmp_path):
        """Test listing checkpoints."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)

        for i in range(3):
            checkpoint = Checkpoint(
                id=f"test-{i}",
                label=f"checkpoint {i}",
                timestamp=time.time(),
                global_state={},
                local_states={},
                metadata={"execution_id": "exec-1"}
            )
            manager.save_checkpoint(checkpoint)

        checkpoints = manager.list_checkpoints("exec-1")
        assert len(checkpoints) == 3

    def test_delete_checkpoint(self, tmp_path):
        """Test deleting a checkpoint."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)

        checkpoint = Checkpoint(
            id="test-1",
            label="test checkpoint",
            timestamp=time.time(),
            global_state={},
            local_states={},
            metadata={"execution_id": "exec-1"}
        )

        manager.save_checkpoint(checkpoint)
        result = manager.delete_checkpoint("test-1", "exec-1")

        assert result is True
        assert manager.load_checkpoint("test-1", "exec-1") is None

    def test_delete_all_checkpoints(self, tmp_path):
        """Test deleting all checkpoints for an execution."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)

        for i in range(3):
            checkpoint = Checkpoint(
                id=f"test-{i}",
                label=f"checkpoint {i}",
                timestamp=time.time(),
                global_state={},
                local_states={},
                metadata={"execution_id": "exec-1"}
            )
            manager.save_checkpoint(checkpoint)

        manager.delete_all_checkpoints("exec-1")

        checkpoints = manager.list_checkpoints("exec-1")
        assert len(checkpoints) == 0

    def test_checkpoint_max_limit(self, tmp_path):
        """Test checkpoint max limit enforcement."""
        manager = CheckpointManager(checkpoint_dir=tmp_path, max_checkpoints=3)

        for i in range(5):
            checkpoint = Checkpoint(
                id=f"test-{i}",
                label=f"checkpoint {i}",
                timestamp=time.time(),
                global_state={},
                local_states={},
                metadata={"execution_id": "exec-1"}
            )
            manager.save_checkpoint(checkpoint)

        checkpoints = manager.list_checkpoints("exec-1")
        assert len(checkpoints) == 3

    def test_checkpoint_multiple_executions(self, tmp_path):
        """Test managing checkpoints for multiple executions."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)

        # Execution 1
        cp1 = Checkpoint(
            id="cp1",
            label="exec1 checkpoint",
            timestamp=time.time(),
            global_state={},
            local_states={},
            metadata={"execution_id": "exec-1"}
        )
        manager.save_checkpoint(cp1)

        # Execution 2
        cp2 = Checkpoint(
            id="cp2",
            label="exec2 checkpoint",
            timestamp=time.time(),
            global_state={},
            local_states={},
            metadata={"execution_id": "exec-2"}
        )
        manager.save_checkpoint(cp2)

        checkpoints1 = manager.list_checkpoints("exec-1")
        checkpoints2 = manager.list_checkpoints("exec-2")

        assert len(checkpoints1) == 1
        assert len(checkpoints2) == 1


class TestCheckpointDataIntegrity:
    """Tests for checkpoint data integrity."""

    def test_checkpoint_global_state_preserved(self, tmp_path):
        """Test global state is preserved in checkpoint."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)

        checkpoint = Checkpoint(
            id="test-1",
            label="test",
            timestamp=time.time(),
            global_state={"var1": "value1", "nested": {"key": "val"}},
            local_states={},
            metadata={}
        )

        manager.save_checkpoint(checkpoint)

        # Reload
        manager2 = CheckpointManager(checkpoint_dir=tmp_path)
        loaded = manager2.load_checkpoint("test-1", "default")

        assert loaded.global_state["var1"] == "value1"
        assert loaded.global_state["nested"]["key"] == "val"

    def test_checkpoint_local_states_preserved(self, tmp_path):
        """Test local states are preserved in checkpoint."""
        manager = CheckpointManager(checkpoint_dir=tmp_path)

        checkpoint = Checkpoint(
            id="test-1",
            label="test",
            timestamp=time.time(),
            global_state={},
            local_states={
                "node1": {"output": "result1"},
                "node2": {"output": "result2"}
            },
            metadata={}
        )

        manager.save_checkpoint(checkpoint)

        # Reload
        manager2 = CheckpointManager(checkpoint_dir=tmp_path)
        loaded = manager2.load_checkpoint("test-1", "default")

        assert loaded.local_states["node1"]["output"] == "result1"
        assert loaded.local_states["node2"]["output"] == "result2"
