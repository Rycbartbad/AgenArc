"""Unit tests for vfs/filesystem.py."""

import pytest
from pathlib import Path
from agenarc.vfs.filesystem import VFS, VFSError


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
        """Test parsing with invalid directory when permissions set to deny."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        # With new model, permissions=None means allow all (backward compatible)
        vfs = VFS(bundle, permissions=None)
        # Should not raise when permissions is None
        directory, filename = vfs._parse_vfs_path("agrc://invalid/system.pt")
        assert directory == "invalid"
        assert filename == "system.pt"

        # When permissions explicitly denies a directory
        vfs_denied = VFS(bundle, permissions={"invalid": "---"})
        with pytest.raises(VFSError, match="Directory not allowed"):
            vfs_denied._parse_vfs_path("agrc://invalid/system.pt")

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
        """Test listing directory contents with directory suffix."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        (prompts_dir / "a.pt").write_text("a")
        (prompts_dir / "b.pt").write_text("b")
        (prompts_dir / "subdir").mkdir()

        vfs = VFS(bundle)
        contents = vfs.list_dir("agrc://prompts")
        assert set(contents) == {"a.pt", "b.pt", "subdir/"}  # directories have / suffix

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


class TestVFSPathTraversal:
    """Tests for VFS path traversal protection."""

    def test_read_path_traversal_blocked(self, tmp_path):
        """Test path traversal is blocked on read."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        vfs = VFS(bundle)
        # Path traversal is blocked - filename validation catches ".." in path
        with pytest.raises(VFSError, match="(Path traversal|Filename contains illegal)"):
            vfs._get_real_path("agrc://prompts/../../../etc/passwd")

    def test_write_path_traversal_blocked(self, tmp_path):
        """Test path traversal is blocked on write."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()

        vfs = VFS(bundle)
        # The path traversal would be blocked in _get_real_path
        with pytest.raises(VFSError, match="(Path traversal|Filename contains illegal)"):
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
        """Test listing nonexistent directory returns empty list."""
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

    def test_list_dir_multi_level_path(self, tmp_path):
        """Test listing subdirectory with multi-level path."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()  # ensure parent exists
        subdir = prompts_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.pt").write_text("nested")

        vfs = VFS(bundle)
        contents = vfs.list_dir("prompts/subdir")
        assert "nested.pt" in contents

    def test_list_dir_path_traversal_raises(self, tmp_path):
        """Test that path traversal raises VFSError."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        vfs = VFS(bundle)
        with pytest.raises(VFSError, match="Path traversal detected"):
            vfs.list_dir("prompts/../../../etc")

    def test_list_dir_permission_denied_raises(self, tmp_path):
        """Test that permission denied raises VFSError."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()

        vfs = VFS(bundle, permissions={"prompts": "---"})  # no read permission
        with pytest.raises(VFSError, match="Permission denied"):
            vfs.list_dir("prompts")

    def test_list_dir_root_lists_top_level(self, tmp_path):
        """Test VFS root lists top-level contents."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()
        (bundle / "manifest.json").write_text("{}")

        vfs = VFS(bundle)
        contents = vfs.list_dir("agrc://")
        assert "prompts/" in contents
        assert "manifest.json" in contents

    def test_list_dir_file_path_returns_empty(self, tmp_path):
        """Test listing a file path (not directory) returns empty list."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "file.pt").write_text("content")

        vfs = VFS(bundle)
        assert vfs.list_dir("prompts/file.pt") == []

    def test_list_dir_results_sorted(self, tmp_path):
        """Test that results are sorted."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "z_file.pt").write_text("z")
        (prompts_dir / "a_file.pt").write_text("a")

        vfs = VFS(bundle)
        contents = vfs.list_dir("prompts")
        assert contents == ["a_file.pt", "z_file.pt"]
