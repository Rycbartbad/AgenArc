"""Unit tests for plugins/loaders/external.py."""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from agenarc.plugins.loaders.external import ExternalPluginLoader, ExternalPluginConfig, ExternalOperatorWrapper


class TestExternalPluginConfig:
    """Tests for ExternalPluginConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = ExternalPluginConfig()

        assert config.protocol == "stdio"
        assert config.command is None
        assert config.url == ""
        assert config.startup_timeout == 10.0
        assert config.request_timeout == 30.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = ExternalPluginConfig(
            protocol="http",
            url="http://localhost:8080",
            startup_timeout=5.0
        )

        assert config.protocol == "http"
        assert config.url == "http://localhost:8080"
        assert config.startup_timeout == 5.0


class TestExternalPluginLoaderInit:
    """Tests for ExternalPluginLoader initialization."""

    def test_creation(self):
        """Test loader creation."""
        loader = ExternalPluginLoader()
        assert loader._processes == {}
        assert loader._configs == {}


class TestExternalPluginLoaderDiscover:
    """Tests for discover method."""

    @pytest.mark.asyncio
    async def test_discover_nonexistent_path(self):
        """Test discover on nonexistent directory."""
        loader = ExternalPluginLoader()
        callback = MagicMock()

        result = await loader.discover(Path("/nonexistent/path"), callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_empty_directory(self, tmp_path):
        """Test discover on empty directory."""
        loader = ExternalPluginLoader()
        callback = MagicMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_skips_directories_without_config(self, tmp_path):
        """Test discover skips directories without agenarc.json."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        loader = ExternalPluginLoader()
        callback = MagicMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_skips_files(self, tmp_path):
        """Test discover skips files (not directories)."""
        # Create a file, not a directory
        plugin_file = tmp_path / "test_plugin.json"
        plugin_file.write_text('{"name": "test"}')

        loader = ExternalPluginLoader()
        callback = MagicMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_skips_non_external_loader(self, tmp_path):
        """Test discover skips non-external loader type."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('''
        {
            "name": "test_plugin",
            "version": "1.0.0",
            "loader": "python"
        }
        ''')

        loader = ExternalPluginLoader()
        callback = MagicMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_skips_invalid_json(self, tmp_path):
        """Test discover skips invalid JSON manifest."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "agenarc.json").write_text("not valid json")

        loader = ExternalPluginLoader()
        callback = MagicMock()

        result = await loader.discover(tmp_path, callback)

        assert result == []

    @pytest.mark.asyncio
    async def test_discover_with_valid_stdio_plugin(self, tmp_path):
        """Test discover finds valid stdio plugin."""
        plugin_dir = tmp_path / "stdio_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('''
        {
            "name": "stdio_plugin",
            "version": "1.0.0",
            "loader": "external",
            "config": {
                "protocol": "stdio",
                "command": ["./plugin"]
            }
        }
        ''')

        loader = ExternalPluginLoader()
        callback = AsyncMock()

        result = await loader.discover(tmp_path, callback)

        assert result == ["stdio_plugin"]


class TestExternalPluginLoaderSendStdioRequest:
    """Tests for _send_stdio_request method."""

    @pytest.mark.asyncio
    async def test_send_stdio_request_process_not_running(self):
        """Test sending request when process not running."""
        loader = ExternalPluginLoader()
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process has terminated
        loader._processes["test"] = mock_process

        result = await loader._send_stdio_request("test", {"method": "test"})

        assert result is None

    @pytest.mark.asyncio
    async def test_send_stdio_request_success(self):
        """Test successful stdio request."""
        loader = ExternalPluginLoader()
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process running
        # Mock readline to return a string directly (not a coroutine)
        mock_process.stdout.readline.return_value = '{"result": "ok"}\n'
        loader._processes["test"] = mock_process

        result = await loader._send_stdio_request("test", {"method": "test"})

        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_send_stdio_request_timeout(self):
        """Test stdio request timeout."""
        loader = ExternalPluginLoader()
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.stdout.readline = AsyncMock(side_effect=asyncio.TimeoutError())
        loader._processes["test"] = mock_process

        result = await loader._send_stdio_request("test", {"method": "test"})

        assert result is None

    @pytest.mark.asyncio
    async def test_send_stdio_request_empty_response(self):
        """Test stdio request with empty response."""
        loader = ExternalPluginLoader()
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.stdout.readline = AsyncMock(return_value="")
        loader._processes["test"] = mock_process

        result = await loader._send_stdio_request("test", {"method": "test"})

        assert result is None


class TestExternalPluginLoaderCallOperator:
    """Tests for call_operator method."""

    @pytest.mark.asyncio
    async def test_call_operator_unknown_plugin(self):
        """Test calling operator on unknown plugin raises."""
        loader = ExternalPluginLoader()

        with pytest.raises(ValueError, match="Unknown plugin"):
            await loader.call_operator("unknown", "op", "execute", {})

    @pytest.mark.asyncio
    async def test_call_operator_stdio_protocol(self):
        """Test calling operator via stdio protocol."""
        loader = ExternalPluginLoader()
        loader._configs["test"] = ExternalPluginConfig(
            protocol="stdio",
            command=["./test"]
        )

        with patch.object(loader, '_call_stdio_operator', new=AsyncMock(return_value={"result": "ok"})) as mock_call:
            mock_call.return_value = {"result": "ok"}
            result = await loader.call_operator("test", "op", "execute", {"input": "data"})

            assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_call_operator_http_protocol(self):
        """Test calling operator via http protocol."""
        loader = ExternalPluginLoader()
        loader._configs["test"] = ExternalPluginConfig(
            protocol="http",
            url="http://localhost:8080"
        )

        with patch.object(loader, '_call_http_operator', new=AsyncMock(return_value={"result": "ok"})) as mock_call:
            mock_call.return_value = {"result": "ok"}
            result = await loader.call_operator("test", "op", "execute", {"input": "data"})

            assert result == {"result": "ok"}


class TestExternalPluginLoaderCallStdioOperator:
    """Tests for _call_stdio_operator method."""

    @pytest.mark.asyncio
    async def test_call_stdio_operator_success(self):
        """Test successful stdio operator call."""
        loader = ExternalPluginLoader()
        loader._processes["test"] = MagicMock()

        with patch.object(loader, '_send_stdio_request', new=AsyncMock(return_value={"result": "success"})):
            result = await loader._call_stdio_operator("test", "op", "execute", {"key": "value"})

            assert result == "success"

    @pytest.mark.asyncio
    async def test_call_stdio_operator_error_response(self):
        """Test stdio operator call with error response."""
        loader = ExternalPluginLoader()
        loader._processes["test"] = MagicMock()

        with patch.object(loader, '_send_stdio_request', new=AsyncMock(return_value={"error": "test error"})):
            with pytest.raises(RuntimeError, match="Plugin error"):
                await loader._call_stdio_operator("test", "op", "execute", {})

    @pytest.mark.asyncio
    async def test_call_stdio_operator_no_response(self):
        """Test stdio operator call with no response."""
        loader = ExternalPluginLoader()
        loader._processes["test"] = MagicMock()

        with patch.object(loader, '_send_stdio_request', new=AsyncMock(return_value=None)):
            with pytest.raises(RuntimeError, match="Plugin call failed"):
                await loader._call_stdio_operator("test", "op", "execute", {})


class TestExternalPluginLoaderLoadHttp:
    """Tests for _load_http_plugin method."""

    @pytest.mark.asyncio
    async def test_load_http_no_url(self):
        """Test load HTTP plugin without URL."""
        loader = ExternalPluginLoader()
        config = ExternalPluginConfig(protocol="http", url="")

        result = await loader._load_http_plugin("test", config)

        assert result == {}

    @pytest.mark.asyncio
    async def test_load_http_success(self):
        """Test successful HTTP plugin load."""
        loader = ExternalPluginLoader()
        config = ExternalPluginConfig(
            protocol="http",
            url="http://localhost:8080"
        )
        loader._configs["test"] = config

        # Mock aiohttp
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"operators": ["op1", "op2"]})

        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await loader._load_http_plugin("test", config)

        assert "op1" in result
        assert "op2" in result

    @pytest.mark.asyncio
    async def test_load_http_health_check_fails(self):
        """Test HTTP plugin load when health check fails."""
        loader = ExternalPluginLoader()
        config = ExternalPluginConfig(
            protocol="http",
            url="http://localhost:8080"
        )

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 503  # Health check failed

        mock_session.get = MagicMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await loader._load_http_plugin("test", config)

        assert result == {}

    @pytest.mark.asyncio
    async def test_load_http_aiohttp_import_error(self):
        """Test HTTP plugin load when aiohttp not available."""
        loader = ExternalPluginLoader()
        config = ExternalPluginConfig(
            protocol="http",
            url="http://localhost:8080"
        )

        with patch.dict("sys.modules", {"aiohttp": None}):
            result = await loader._load_http_plugin("test", config)

        assert result == {}


class TestExternalPluginLoaderCallHttpOperator:
    """Tests for _call_http_operator method."""

    @pytest.mark.asyncio
    async def test_call_http_operator_unknown_plugin(self):
        """Test HTTP operator call with unknown plugin."""
        loader = ExternalPluginLoader()
        # No config for "unknown"

        with pytest.raises(ValueError, match="Unknown plugin"):
            await loader._call_http_operator("unknown", "op", "execute", {})


class TestExternalPluginLoaderLoadStdio:
    """Tests for _load_stdio_plugin method."""

    @pytest.mark.asyncio
    async def test_load_stdio_no_command(self):
        """Test load stdio plugin without command."""
        loader = ExternalPluginLoader()
        config = ExternalPluginConfig(protocol="stdio", command=None)

        result = await loader._load_stdio_plugin("test", config)

        assert result == {}

    @pytest.mark.asyncio
    async def test_load_stdio_subprocess_error(self):
        """Test load stdio plugin with subprocess error."""
        loader = ExternalPluginLoader()
        config = ExternalPluginConfig(
            protocol="stdio",
            command=["./nonexistent"]
        )

        with patch("subprocess.Popen", side_effect=FileNotFoundError()):
            result = await loader._load_stdio_plugin("test", config)

        assert result == {}


class TestExternalPluginLoaderUnload:
    """Tests for unload method."""

    def test_unload_nonexistent(self):
        """Test unloading nonexistent plugin."""
        loader = ExternalPluginLoader()

        result = loader.unload("nonexistent")

        assert result is False

    def test_unload_stops_process(self):
        """Test unloading stops the plugin process."""
        loader = ExternalPluginLoader()
        mock_process = MagicMock()
        mock_process.wait.return_value = None
        loader._processes["test"] = mock_process

        result = loader.unload("test")

        assert result is True
        mock_process.terminate.assert_called_once()
        assert "test" not in loader._processes

    def test_unload_removes_config(self):
        """Test unloading removes config for unloaded plugin."""
        loader = ExternalPluginLoader()
        loader._configs["test"] = ExternalPluginConfig()

        result = loader.unload("test")

        assert result is True
        assert "test" not in loader._configs


class TestExternalOperatorWrapper:
    """Tests for ExternalOperatorWrapper."""

    @pytest.mark.asyncio
    async def test_execute_delegates_to_loader(self):
        """Test execute calls loader.call_operator."""
        loader = ExternalPluginLoader()
        wrapper = ExternalOperatorWrapper(
            plugin_name="test",
            operator_name="op",
            loader=loader
        )

        with patch.object(loader, 'call_operator', new=AsyncMock(return_value={"result": "ok"})) as mock_call:
            result = await wrapper.execute({"input": "data"}, None)

            mock_call.assert_called_once_with(
                "test", "op", "execute", {"inputs": {"input": "data"}, "context": {}}
            )
            assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_validate_delegates_to_loader(self):
        """Test validate calls loader.call_operator."""
        loader = ExternalPluginLoader()
        wrapper = ExternalOperatorWrapper(
            plugin_name="test",
            operator_name="op",
            loader=loader
        )

        with patch.object(loader, 'call_operator', new=AsyncMock(return_value=True)) as mock_call:
            result = await wrapper.validate({"input": "data"})

            mock_call.assert_called_once_with(
                "test", "op", "validate", {"inputs": {"input": "data"}}
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_returns_false_on_error(self):
        """Test validate returns False on error."""
        loader = ExternalPluginLoader()
        wrapper = ExternalOperatorWrapper(
            plugin_name="test",
            operator_name="op",
            loader=loader
        )

        with patch.object(loader, 'call_operator', new=AsyncMock(side_effect=Exception("error"))):
            result = await wrapper.validate({"input": "data"})

            assert result is False

    def test_name_property(self):
        """Test name property returns operator name."""
        loader = ExternalPluginLoader()
        wrapper = ExternalOperatorWrapper(
            plugin_name="test",
            operator_name="my_operator",
            loader=loader
        )

        assert wrapper.name == "test.my_operator"
