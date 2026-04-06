"""Unit tests for operators/evolution.py."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from agenarc.operators.evolution import (
    Asset_Reader_Operator,
    Asset_Writer_Operator,
    Runtime_Reload_Operator,
    get_evolution_operators,
)
from agenarc.engine.state import StateManager, ExecutionContext


def create_context(bundle_path=None):
    """Create a test execution context."""
    sm = StateManager()
    sm.initialize("test_exec", "test_graph")
    ctx = ExecutionContext(sm)
    if bundle_path:
        ctx.set("_bundle_path", bundle_path)
    return ctx


class TestAssetReaderOperator:
    """Tests for Asset_Reader_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Asset_Reader_Operator()
        assert op.name == "builtin.asset_reader"

    def test_description(self):
        """Test operator description."""
        op = Asset_Reader_Operator()
        assert "VFS" in op.description

    def test_input_ports(self):
        """Test input ports."""
        op = Asset_Reader_Operator()
        ports = op.get_input_ports()
        port_names = {p.name for p in ports}
        assert "path" in port_names
        assert "encoding" in port_names

    def test_output_ports(self):
        """Test output ports."""
        op = Asset_Reader_Operator()
        ports = op.get_output_ports()
        port_names = {p.name for p in ports}
        assert "content" in port_names
        assert "success" in port_names
        assert "metadata" in port_names

    @pytest.mark.asyncio
    async def test_read_empty_path(self):
        """Test reading with empty path."""
        op = Asset_Reader_Operator()
        ctx = create_context()

        result = await op.execute({}, ctx)

        assert result["success"] is False
        assert result["content"] == ""

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, tmp_path):
        """Test reading nonexistent file."""
        bundle = tmp_path / "test.arc"
        bundle.mkdir()
        (bundle / "prompts").mkdir()

        op = Asset_Reader_Operator()
        ctx = create_context(bundle)

        result = await op.execute({"path": "arc://prompts/nonexistent.pt"}, ctx)

        assert result["success"] is False


class TestAssetWriterOperator:
    """Tests for Asset_Writer_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Asset_Writer_Operator()
        assert op.name == "builtin.asset_writer"

    def test_description(self):
        """Test operator description."""
        op = Asset_Writer_Operator()
        assert "VFS" in op.description

    def test_input_ports(self):
        """Test input ports."""
        op = Asset_Writer_Operator()
        ports = op.get_input_ports()
        port_names = {p.name for p in ports}
        assert "path" in port_names
        assert "content" in port_names
        assert "operation" in port_names

    def test_output_ports(self):
        """Test output ports."""
        op = Asset_Writer_Operator()
        ports = op.get_output_ports()
        port_names = {p.name for p in ports}
        assert "success" in port_names
        assert "path" in port_names
        assert "error" in port_names

    @pytest.mark.asyncio
    async def test_write_empty_path(self):
        """Test writing with empty path."""
        op = Asset_Writer_Operator()
        ctx = create_context()

        result = await op.execute({"content": "test"}, ctx)

        assert result["success"] is False
        assert "Path is required" in result["error"]

    @pytest.mark.asyncio
    async def test_write_to_valid_path(self, tmp_path):
        """Test writing to valid path."""
        bundle = tmp_path / "test.arc"
        bundle.mkdir()
        scripts_dir = bundle / "scripts"
        scripts_dir.mkdir()

        op = Asset_Writer_Operator()
        ctx = create_context(bundle)

        result = await op.execute({
            "path": "arc://scripts/new_file.py",
            "content": "print('hello')"
        }, ctx)

        assert result["success"] is True
        assert result["path"] == "arc://scripts/new_file.py"

        # Verify file was written
        new_file = scripts_dir / "new_file.py"
        assert new_file.exists()
        assert new_file.read_text() == "print('hello')"

    @pytest.mark.asyncio
    async def test_write_update_existing_file(self, tmp_path):
        """Test updating existing file via VFS."""
        bundle = tmp_path / "test.arc"
        bundle.mkdir()
        scripts_dir = bundle / "scripts"
        scripts_dir.mkdir()

        # Create existing file
        existing = scripts_dir / "existing.py"
        existing.write_text("original")

        op = Asset_Writer_Operator()
        ctx = create_context(bundle)

        result = await op.execute({
            "path": "arc://scripts/existing.py",
            "content": "updated",
            "operation": "update"
        }, ctx)

        assert result["success"] is True
        assert existing.read_text() == "updated"

    @pytest.mark.asyncio
    async def test_write_delete_operation(self, tmp_path):
        """Test delete operation returns not implemented."""
        bundle = tmp_path / "test.arc"
        bundle.mkdir()
        scripts_dir = bundle / "scripts"
        scripts_dir.mkdir()

        op = Asset_Writer_Operator()
        ctx = create_context(bundle)

        result = await op.execute({
            "path": "arc://scripts/file.py",
            "operation": "delete"
        }, ctx)

        assert result["success"] is False
        assert "not implemented" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_write_file_already_exists(self, tmp_path):
        """Test writing file that already exists."""
        bundle = tmp_path / "test.arc"
        bundle.mkdir()
        scripts_dir = bundle / "scripts"
        scripts_dir.mkdir()

        existing = scripts_dir / "existing.py"
        existing.write_text("original")

        op = Asset_Writer_Operator()
        ctx = create_context(bundle)

        result = await op.execute({
            "path": "arc://scripts/existing.py",
            "content": "new content"
        }, ctx)

        assert result["success"] is False
        assert "already exists" in result["error"]

    @pytest.mark.asyncio
    async def test_write_immutable_path(self, tmp_path):
        """Test writing to immutable path is blocked."""
        bundle = tmp_path / "test.arc"
        bundle.mkdir()
        scripts_dir = bundle / "scripts"
        scripts_dir.mkdir()

        op = Asset_Writer_Operator()
        ctx = create_context(bundle)
        ctx.set("_immutable_nodes", ["arc://scripts/immutable.py"])

        result = await op.execute({
            "path": "arc://scripts/immutable.py",
            "content": "cannot write"
        }, ctx)

        assert result["success"] is False
        assert "immutable" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_read_file_with_encoding(self, tmp_path):
        """Test reading file with specific encoding."""
        bundle = tmp_path / "test.arc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        test_file = prompts_dir / "test.txt"
        test_file.write_text("Hello", encoding="utf-8")

        op = Asset_Reader_Operator()
        ctx = create_context(bundle)

        result = await op.execute({
            "path": "arc://prompts/test.txt",
            "encoding": "utf-8"
        }, ctx)

        assert result["success"] is True
        assert result["content"] == "Hello"
        assert "size" in result["metadata"]

    @pytest.mark.asyncio
    async def test_read_returns_metadata(self, tmp_path):
        """Test read returns file metadata."""
        bundle = tmp_path / "test.arc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        test_file = prompts_dir / "test.pt"
        test_file.write_text("content")

        op = Asset_Reader_Operator()
        ctx = create_context(bundle)

        result = await op.execute({"path": "arc://prompts/test.pt"}, ctx)

        assert result["success"] is True
        assert "metadata" in result
        assert "path" in result["metadata"]


class TestRuntimeReloadOperator:
    """Tests for Runtime_Reload_Operator."""

    def test_name(self):
        """Test operator name."""
        op = Runtime_Reload_Operator()
        assert op.name == "builtin.runtime_reload"

    def test_description(self):
        """Test operator description."""
        op = Runtime_Reload_Operator()
        assert "reload" in op.description.lower()

    def test_input_ports(self):
        """Test input ports."""
        op = Runtime_Reload_Operator()
        ports = op.get_input_ports()
        assert len(ports) == 1
        assert ports[0].name == "target"

    def test_output_ports(self):
        """Test output ports."""
        op = Runtime_Reload_Operator()
        ports = op.get_output_ports()
        port_names = {p.name for p in ports}
        assert "success" in port_names
        assert "reloaded_scripts" in port_names
        assert "error" in port_names

    @pytest.mark.asyncio
    async def test_reload_plugins(self):
        """Test reloading plugins."""
        op = Runtime_Reload_Operator()
        ctx = create_context()

        result = await op.execute({"target": "plugins"}, ctx)

        assert result["success"] is True
        assert "plugins" in result["reloaded_scripts"]

    @pytest.mark.asyncio
    async def test_reload_both(self):
        """Test reloading both."""
        op = Runtime_Reload_Operator()
        ctx = create_context()

        result = await op.execute({"target": "both"}, ctx)

        assert result["success"] is True


class TestGetEvolutionOperators:
    """Tests for get_evolution_operators function."""

    def test_returns_dict(self):
        """Test returns dictionary of operators."""
        operators = get_evolution_operators()
        assert isinstance(operators, dict)

    def test_contains_expected_operators(self):
        """Test contains expected operator types."""
        operators = get_evolution_operators()
        assert "Asset_Reader" in operators
        assert "Asset_Writer" in operators
        assert "Runtime_Reload" in operators

    def test_are_classes(self):
        """Test values are operator classes."""
        operators = get_evolution_operators()
        for op_class in operators.values():
            assert op_class is not None
            assert hasattr(op_class, "execute")
