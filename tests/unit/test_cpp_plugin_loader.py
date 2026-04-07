"""Unit tests for plugins/loaders/cpp.py."""

import pytest
import sys
import ctypes
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from agenarc.plugins.loaders.cpp import CppPluginLoader, CppOperatorWrapper


class TestCppPluginLoaderInit:
    """Tests for CppPluginLoader initialization."""

    def test_creation(self):
        """Test loader creation."""
        loader = CppPluginLoader()
        assert loader._libraries == {}
        assert loader._factories == {}

    def test_library_extension_windows(self):
        """Test Windows library extension."""
        loader = CppPluginLoader()
        with patch.object(sys, 'platform', 'win32'):
            ext = loader._get_library_extension()
            assert ext == ".dll"

    def test_library_extension_macos(self):
        """Test macOS library extension."""
        loader = CppPluginLoader()
        with patch.object(sys, 'platform', 'darwin'):
            ext = loader._get_library_extension()
            assert ext == ".dylib"

    def test_library_extension_linux(self):
        """Test Linux library extension."""
        loader = CppPluginLoader()
        with patch.object(sys, 'platform', 'linux'):
            ext = loader._get_library_extension()
            assert ext == ".so"


class TestCppPluginLoaderDiscover:
    """Tests for discover method."""

    @pytest.mark.asyncio
    async def test_discover_nonexistent_path(self):
        """Test discover on nonexistent directory."""
        loader = CppPluginLoader()
        callback = MagicMock()

        result = await loader.discover(Path("/nonexistent/path"), callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_empty_directory(self, tmp_path):
        """Test discover on empty directory."""
        loader = CppPluginLoader()
        callback = MagicMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_skips_directories_without_library(self, tmp_path):
        """Test discover skips directories without library file."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "agenarc.json").write_text('{"name": "test"}')

        loader = CppPluginLoader()
        callback = MagicMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_skips_invalid_json(self, tmp_path):
        """Test discover skips invalid JSON manifest."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "agenarc.json").write_text("not valid json")

        loader = CppPluginLoader()
        callback = MagicMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_with_valid_plugin(self, tmp_path):
        """Test discover with valid plugin."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = {
            "name": "test_plugin",
            "version": "1.0.0",
            "library": "libtest.dll"
        }
        (plugin_dir / "agenarc.json").write_text('{"name": "test_plugin", "version": "1.0.0", "library": "libtest.dll"}')

        # Create a dummy library file (empty, just for exists check)
        lib_file = plugin_dir / "libtest.dll"
        lib_file.write_bytes(b"")

        loader = CppPluginLoader()
        callback = AsyncMock()

        result = await loader.discover(tmp_path, callback)

        assert result == ["test_plugin"]
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args.name == "test_plugin"
        assert call_args.loader_type == "cpp"


class TestCppPluginLoaderLoad:
    """Tests for load method."""

    @pytest.mark.asyncio
    async def test_load_creates_operators(self, tmp_path):
        """Test load creates operator wrappers."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = {
            "name": "test_plugin",
            "version": "1.0.0",
            "library": "libtest.dll",
            "symbols": ["operator1"]
        }
        (plugin_dir / "agenarc.json").write_text('{"name": "test_plugin", "version": "1.0.0", "library": "libtest.dll", "symbols": ["operator1"]}')

        # Create a dummy library file
        lib_file = plugin_dir / "libtest.dll"
        lib_file.write_bytes(b"")

        plugin_info = MagicMock()
        plugin_info.name = "test_plugin"
        plugin_info.path = lib_file

        loader = CppPluginLoader()

        # Mock ctypes.CDLL
        mock_library = MagicMock()
        mock_factory = MagicMock()
        mock_factory.restype = ctypes.c_void_p
        mock_factory.return_value = 12345
        mock_library.create_operator1 = mock_factory
        mock_library.destroy_operator1 = MagicMock()

        with patch("ctypes.CDLL", return_value=mock_library):
            result = await loader.load(plugin_info)

        assert "operator1" in result
        assert isinstance(result["operator1"], CppOperatorWrapper)

    @pytest.mark.asyncio
    async def test_load_library_error(self, tmp_path):
        """Test load handles library loading error."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "agenarc.json").write_text('{"name": "test", "library": "nonexistent.dll"}')

        lib_file = plugin_dir / "nonexistent.dll"
        lib_file.write_bytes(b"")

        plugin_info = MagicMock()
        plugin_info.name = "test"
        plugin_info.path = lib_file

        loader = CppPluginLoader()

        with patch("ctypes.CDLL", side_effect=OSError("Cannot load")):
            result = await loader.load(plugin_info)

        assert result == {}


class TestCppPluginLoaderUnload:
    """Tests for unload method."""

    def test_unload_existing_library(self):
        """Test unloading existing library."""
        loader = CppPluginLoader()
        # Create a mock library-like object
        class MockLib:
            _handle = 12345
        loader._libraries["test"] = MockLib()

        # Mock FreeLibrary to avoid actual system call
        with patch("ctypes.windll.kernel32.FreeLibrary", return_value=True):
            result = loader.unload("test")

        assert result is True
        assert "test" not in loader._libraries

    def test_unload_nonexistent_library(self):
        """Test unloading nonexistent library."""
        loader = CppPluginLoader()

        result = loader.unload("nonexistent")

        assert result is False

    def test_unload_library_error_windows(self):
        """Test unloading with Windows error."""
        loader = CppPluginLoader()

        class MockLib:
            _handle = 12345
        mock_lib = MockLib()
        loader._libraries["test"] = mock_lib

        with patch("ctypes.windll.kernel32.FreeLibrary", side_effect=Exception("Failed")):
            result = loader.unload("test")

        # Even if FreeLibrary fails, the library is removed from dict
        assert "test" not in loader._libraries

    def test_unload_library_error_unix(self):
        """Test unloading with Unix error."""
        loader = CppPluginLoader()

        class MockLib:
            _handle = 12345
        mock_lib = MockLib()
        loader._libraries["test"] = mock_lib

        with patch("sys.platform", "linux"):
            with patch("ctypes.cdll.LoadLibrary", side_effect=Exception("Failed")):
                result = loader.unload("test")

        assert "test" not in loader._libraries


class TestCppOperatorWrapper:
    """Tests for CppOperatorWrapper."""

    def test_creation(self):
        """Test wrapper creation."""
        mock_lib = MagicMock()
        wrapper = CppOperatorWrapper(
            library=mock_lib,
            destructor_name="destroy_test",
            operator_ptr=12345,
            symbol_name="test"
        )
        assert wrapper._operator_ptr == 12345
        assert wrapper._symbol_name == "test"
        assert wrapper._destroyed is False

    def test_call_method_success(self):
        """Test calling a method on the wrapper."""
        mock_lib = MagicMock()
        mock_method = MagicMock(return_value="result")
        mock_lib.test_op = mock_method

        wrapper = CppOperatorWrapper(
            library=mock_lib,
            destructor_name="destroy_test",
            operator_ptr=12345,
            symbol_name="test"
        )

        result = wrapper.call_method("op")

        mock_method.assert_called_once_with(12345)
        assert result == "result"

    def test_call_method_destroyed(self):
        """Test calling method on destroyed wrapper raises."""
        mock_lib = MagicMock()
        wrapper = CppOperatorWrapper(
            library=mock_lib,
            destructor_name="destroy_test",
            operator_ptr=12345,
            symbol_name="test"
        )
        wrapper._destroyed = True

        with pytest.raises(RuntimeError, match="destroyed"):
            wrapper.call_method("op")

    def test_call_method_not_found(self):
        """Test calling nonexistent method raises."""
        mock_lib = MagicMock(spec=[])  # Empty spec means no attributes
        wrapper = CppOperatorWrapper(
            library=mock_lib,
            destructor_name="destroy_test",
            operator_ptr=12345,
            symbol_name="test"
        )

        with pytest.raises(AttributeError, match="Method not found"):
            wrapper.call_method("nonexistent")

    def test_del_destructor(self):
        """Test destructor calls destroy."""
        mock_lib = MagicMock()
        mock_destructor = MagicMock()
        mock_lib.destroy_test = mock_destructor

        wrapper = CppOperatorWrapper(
            library=mock_lib,
            destructor_name="destroy_test",
            operator_ptr=12345,
            symbol_name="test"
        )

        # Call __del__ implicitly
        wrapper.__del__()

        mock_destructor.assert_called_once_with(12345)
        assert wrapper._destroyed is True

    def test_del_already_destroyed(self):
        """Test destructor doesn't double destroy."""
        mock_lib = MagicMock()
        wrapper = CppOperatorWrapper(
            library=mock_lib,
            destructor_name="destroy_test",
            operator_ptr=12345,
            symbol_name="test"
        )
        wrapper._destroyed = True

        # Should not raise
        wrapper.__del__()

        # Destructor should not have been called
        assert not hasattr(mock_lib, 'destroy_test') or mock_lib.destroy_test.called is False
