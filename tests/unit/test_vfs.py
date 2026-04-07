"""Unit tests for vfs/filesystem.py."""

import pytest
from pathlib import Path
from agenarc.vfs.filesystem import VFS, VFSError, resolve_agrc_path


class TestVFS:
    """Tests for VFS."""

    def test_vfs_creation(self, tmp_path):
        """Test VFS can be created with bundle path."""
        # Create bundle structure
        bundle = tmp_path / "test_agent.agrc"
        bundle.mkdir()
        (bundle / "prompts").mkdir()

        vfs = VFS(bundle)
        assert vfs.bundle_path == bundle

    def test_vfs_nonexistent_bundle(self, tmp_path):
        """Test VFS raises error for nonexistent bundle."""
        with pytest.raises(VFSError, match="Bundle not found"):
            VFS(tmp_path / "nonexistent.agrc")

    def test_vfs_file_not_directory(self, tmp_path):
        """Test VFS raises error if path is not a directory."""
        file_path = tmp_path / "some_file.txt"
        file_path.write_text("content")

        with pytest.raises(VFSError, match="must be a directory"):
            VFS(file_path)

    def test_parse_vfs_path(self, tmp_path):
        """Test parsing VFS paths."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        vfs = VFS(bundle)

        directory, filename = vfs._parse_vfs_path("agrc://prompts/system.pt")
        assert directory == "prompts"
        assert filename == "system.pt"

    def test_parse_vfs_path_invalid_scheme(self, tmp_path):
        """Test parsing invalid VFS scheme."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        vfs = VFS(bundle)

        with pytest.raises(VFSError, match="must start with"):
            vfs._parse_vfs_path("/prompts/system.pt")

    def test_parse_vfs_path_invalid_directory(self, tmp_path):
        """Test parsing with invalid directory."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        vfs = VFS(bundle)

        with pytest.raises(VFSError, match="Directory not allowed"):
            vfs._parse_vfs_path("agrc://invalid/system.pt")

    def test_read_file(self, tmp_path):
        """Test reading file via VFS."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        test_file = prompts_dir / "test.pt"
        test_file.write_text("Hello {{name}}", encoding="utf-8")

        vfs = VFS(bundle)
        content = vfs.read("agrc://prompts/test.pt")
        assert content == "Hello {{name}}"

    def test_read_nonexistent_file(self, tmp_path):
        """Test reading nonexistent file raises error."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        vfs = VFS(bundle)
        with pytest.raises(VFSError, match="File not found"):
            vfs.read("agrc://prompts/nonexistent.pt")

    def test_write_file(self, tmp_path):
        """Test writing file via VFS."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        scripts_dir = bundle / "scripts"
        scripts_dir.mkdir()

        vfs = VFS(bundle)
        vfs.write("agrc://scripts/test.py", "print('hello')")

        test_file = scripts_dir / "test.py"
        assert test_file.exists()
        assert test_file.read_text() == "print('hello')"

    def test_write_creates_parent_dirs(self, tmp_path):
        """Test writing creates parent directories."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()

        vfs = VFS(bundle)
        vfs.write("agrc://prompts/new_file.pt", "content")

        new_file = bundle / "prompts" / "new_file.pt"
        assert new_file.exists()

    def test_exists(self, tmp_path):
        """Test exists check."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        test_file = prompts_dir / "exists.pt"
        test_file.write_text("exists")

        vfs = VFS(bundle)
        assert vfs.exists("agrc://prompts/exists.pt") is True
        assert vfs.exists("agrc://prompts/nonexistent.pt") is False

    def test_list_dir(self, tmp_path):
        """Test listing directory contents."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        (prompts_dir / "a.pt").write_text("a")
        (prompts_dir / "b.pt").write_text("b")

        vfs = VFS(bundle)
        contents = vfs.list_dir("agrc://prompts")
        assert set(contents) == {"a.pt", "b.pt"}

    def test_render_template(self, tmp_path):
        """Test template rendering."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        template_file = prompts_dir / "template.pt"
        template_file.write_text("Hello {{name}}, you have {{count}} messages")

        vfs = VFS(bundle)
        result = vfs.render_template(
            "agrc://prompts/template.pt",
            {"name": "Alice", "count": 5}
        )
        assert result == "Hello Alice, you have 5 messages"


class TestResolveAgrcPath:
    """Tests for resolve_agrc_path function."""

    def test_resolve_valid_path(self, tmp_path):
        """Test resolving valid VFS path."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "test.pt").write_text("content")

        result = resolve_agrc_path("agrc://prompts/test.pt", bundle)
        assert result is not None
        assert result.name == "test.pt"

    def test_resolve_invalid_scheme(self, tmp_path):
        """Test resolving path without agrc:// scheme."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()

        result = resolve_agrc_path("/prompts/test.pt", bundle)
        assert result is None

    def test_resolve_invalid_directory(self, tmp_path):
        """Test resolving path with invalid directory."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()

        result = resolve_agrc_path("agrc://invalid/test.pt", bundle)
        assert result is None

    def test_resolve_flow_json(self, tmp_path):
        """Test resolving flow.json."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        flow_file = bundle / "flow.json"
        flow_file.write_text("{}")

        result = resolve_agrc_path("agrc://flow.json", bundle)
        assert result is not None
        assert result == flow_file

    def test_resolve_path_traversal(self, tmp_path):
        """Test path traversal is blocked."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()

        result = resolve_agrc_path("agrc://prompts/../../../etc/passwd", bundle)
        assert result is None

    def test_resolve_path_single_part(self, tmp_path):
        """Test resolving path with only directory (no file)."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()

        result = resolve_agrc_path("agrc://prompts", bundle)
        assert result is None


class TestVFSPathTraversal:
    """Tests for VFS path traversal protection."""

    def test_read_path_traversal_blocked(self, tmp_path):
        """Test path traversal is blocked on read."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        vfs = VFS(bundle)
        with pytest.raises(VFSError, match="Path traversal detected"):
            vfs._get_real_path("agrc://prompts/../../../etc/passwd")

    def test_write_path_traversal_blocked(self, tmp_path):
        """Test path traversal is blocked on write."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()

        vfs = VFS(bundle)
        # The path traversal would be blocked in _get_real_path
        with pytest.raises(VFSError, match="Path traversal detected"):
            vfs._get_real_path("agrc://scripts/../../../etc/passwd")


class TestVFSReadWrite:
    """Tests for VFS read/write with encoding."""

    def test_read_file_with_encoding(self, tmp_path):
        """Test reading file with specific encoding."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        test_file = prompts_dir / "test.txt"
        test_file.write_text("Hello", encoding="utf-8")

        vfs = VFS(bundle)
        content = vfs.read("agrc://prompts/test.txt", encoding="utf-8")
        assert content == "Hello"

    def test_write_file_with_encoding(self, tmp_path):
        """Test writing file with specific encoding."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        scripts_dir = bundle / "scripts"
        scripts_dir.mkdir()

        vfs = VFS(bundle)
        vfs.write("agrc://scripts/test.txt", "Hello", encoding="utf-8")

        test_file = scripts_dir / "test.txt"
        assert test_file.exists()

    def test_read_not_a_file(self, tmp_path):
        """Test reading a directory as file raises error."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        vfs = VFS(bundle)
        # Trying to read agrc://prompts (directory as file) fails at parsing
        with pytest.raises(VFSError, match="Invalid VFS path"):
            vfs.read("agrc://prompts")

    def test_exists_on_path_traversal(self, tmp_path):
        """Test exists returns False for path traversal."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        vfs = VFS(bundle)
        assert vfs.exists("agrc://prompts/../../../etc/passwd") is False


class TestVFSListDir:
    """Tests for VFS list_dir."""

    def test_list_dir_nonexistent(self, tmp_path):
        """Test listing nonexistent directory."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()

        vfs = VFS(bundle)
        contents = vfs.list_dir("agrc://prompts")
        assert contents == []

    def test_list_dir_without_scheme(self, tmp_path):
        """Test listing directory without scheme prefix."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "test.pt").write_text("content")

        vfs = VFS(bundle)
        contents = vfs.list_dir("prompts")
        assert "test.pt" in contents
