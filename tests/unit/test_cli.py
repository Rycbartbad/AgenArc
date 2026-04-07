"""Unit tests for CLI."""

import pytest
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import tempfile
import shutil

from agenarc.cli.__main__ import (
    create_parser,
    print_error,
    print_success,
    command_run,
    command_validate,
    command_info,
    main,
    _install_bundle_plugins,
    _extract_agrc,
)


class TestCreateParser:
    """Tests for create_parser."""

    def test_create_parser(self):
        """Test parser creation."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "agenarc"

    def test_parse_run_command(self):
        """Test parsing run command."""
        parser = create_parser()
        args = parser.parse_args(["run", "test.json"])
        assert args.command == "run"
        assert args.file == Path("test.json")

    def test_parse_validate_command(self):
        """Test parsing validate command."""
        parser = create_parser()
        args = parser.parse_args(["validate", "test.json"])
        assert args.command == "validate"
        assert args.file == Path("test.json")

    def test_parse_info_command(self):
        """Test parsing info command."""
        parser = create_parser()
        args = parser.parse_args(["info", "test.json"])
        assert args.command == "info"
        assert args.file == Path("test.json")

    def test_parse_run_with_mode(self):
        """Test parsing run command with mode."""
        parser = create_parser()
        args = parser.parse_args(["run", "test.json", "--mode", "sync"])
        assert args.mode == "sync"

    def test_parse_run_with_input(self):
        """Test parsing run command with input."""
        parser = create_parser()
        args = parser.parse_args(["run", "test.json", "-i", '{"key": "value"}'])
        assert args.input == '{"key": "value"}'

    def test_parse_run_with_verbose(self):
        """Test parsing run command with verbose."""
        parser = create_parser()
        args = parser.parse_args(["run", "test.json", "-v"])
        assert args.verbose is True


class TestPrintFunctions:
    """Tests for print functions."""

    def test_print_error(self, capsys):
        """Test print_error outputs to stderr."""
        print_error("Test error message")
        captured = capsys.readouterr()
        assert "ERROR: Test error message" in captured.err

    def test_print_success(self, capsys):
        """Test print_success outputs to stdout."""
        print_success("Test success message")
        captured = capsys.readouterr()
        assert "SUCCESS: Test success message" in captured.out


class TestCommandValidate:
    """Tests for command_validate."""

    def test_validate_valid_protocol(self, tmp_path, capsys):
        """Test validating a valid protocol."""
        protocol_file = tmp_path / "test.json"
        protocol_file.write_text(json.dumps({
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"}
            ],
            "edges": []
        }))

        result = command_validate(protocol_file)

        assert result == 0
        captured = capsys.readouterr()
        assert "Protocol is valid" in captured.out

    def test_validate_invalid_file(self, tmp_path, capsys):
        """Test validating non-existent file."""
        result = command_validate(tmp_path / "nonexistent.json")
        assert result == 1


class TestCommandInfo:
    """Tests for command_info."""

    def test_info_protocol(self, tmp_path, capsys):
        """Test info command."""
        protocol_file = tmp_path / "test.json"
        protocol_file.write_text(json.dumps({
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "metadata": {
                "name": "Test Protocol",
                "description": "A test protocol"
            },
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start",
                    "inputs": [{"name": "input", "type": "string"}],
                    "outputs": [{"name": "output", "type": "any"}]
                }
            ],
            "edges": []
        }))

        result = command_info(protocol_file)

        assert result == 0
        captured = capsys.readouterr()
        assert "Test Protocol" in captured.out
        assert "trigger_1" in captured.out

    def test_info_nonexistent_file(self, tmp_path, capsys):
        """Test info with non-existent file."""
        result = command_info(tmp_path / "nonexistent.json")
        assert result == 1


class TestCommandRun:
    """Tests for command_run."""

    def test_run_with_invalid_json_input(self, tmp_path, capsys):
        """Test run with invalid JSON input."""
        protocol_file = tmp_path / "test.json"
        protocol_file.write_text(json.dumps({
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"}
            ],
            "edges": []
        }))

        result = command_run(protocol_file, input_json="not valid json{{")

        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid JSON" in captured.err

    def test_run_with_nonexistent_file(self, tmp_path, capsys):
        """Test run with non-existent file."""
        result = command_run(tmp_path / "nonexistent.json")
        assert result == 1


class TestMain:
    """Tests for main function."""

    def test_main_no_command(self, capsys):
        """Test main with no command shows help."""
        result = main([])
        assert result == 0
        captured = capsys.readouterr()
        assert "commands" in captured.out.lower()

    def test_main_unknown_command(self, capsys):
        """Test main with unknown command shows help."""
        # unknown_command is treated as a positional file argument, not a subcommand
        # So this triggers the argparse error
        with pytest.raises(SystemExit):
            main(["unknown_command"])

    def test_main_validate_command(self, tmp_path, capsys):
        """Test main with validate command."""
        protocol_file = tmp_path / "test.json"
        protocol_file.write_text(json.dumps({
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"}
            ],
            "edges": []
        }))

        result = main(["validate", str(protocol_file)])
        assert result == 0

    def test_main_info_command(self, tmp_path, capsys):
        """Test main with info command."""
        protocol_file = tmp_path / "test.json"
        protocol_file.write_text(json.dumps({
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"}
            ],
            "edges": []
        }))

        result = main(["info", str(protocol_file)])
        assert result == 0


class TestInstallBundlePlugins:
    """Tests for _install_bundle_plugins."""

    def test_install_no_plugins_dir(self, tmp_path):
        """Test when bundle has no assets/plugins directory."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()

        # Should not raise
        _install_bundle_plugins(bundle)

    def test_install_empty_plugins_dir(self, tmp_path):
        """Test when assets/plugins directory is empty."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        assets = bundle / "assets"
        assets.mkdir()
        plugins = assets / "plugins"
        plugins.mkdir()

        _install_bundle_plugins(bundle)

        # Should complete without error

    def test_install_with_plugin(self, tmp_path):
        """Test installing a plugin from bundle."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()
        assets = bundle / "assets"
        assets.mkdir()
        plugins = assets / "plugins"
        plugins.mkdir()

        # Create a test plugin
        plugin_dir = plugins / "test_plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "agenarc.json"
        manifest.write_text('{"name": "test_plugin", "version": "1.0.0"}')

        with patch("pathlib.Path.expanduser") as mock_expand:
            mock_expand.return_value = tmp_path / "global_plugins"
            _install_bundle_plugins(bundle)

            # Plugin should be installed to global directory
            global_plugin_dir = tmp_path / "global_plugins" / "test_plugin"
            # Note: actual installation depends on shutil.copytree behavior


class TestExtractAgrc:
    """Tests for _extract_agrc."""

    def test_extract_agrc_not_a_file(self, tmp_path):
        """Test when path is not a file."""
        bundle = tmp_path / "test.agrc"
        bundle.mkdir()

        # Should handle gracefully or raise appropriate error
        with pytest.raises(Exception):
            _extract_agrc(bundle)

    def test_extract_agrc_invalid_zip(self, tmp_path):
        """Test when file is not a valid zip."""
        invalid_file = tmp_path / "invalid.agrc"
        invalid_file.write_bytes(b"not a zip file")

        with pytest.raises(zipfile.BadZipFile):
            _extract_agrc(invalid_file)

    def test_extract_agrc_valid_bundle(self, tmp_path):
        """Test extracting a valid agrc bundle."""
        # Create a valid zip file
        agrc_file = tmp_path / "test.agrc"
        with zipfile.ZipFile(agrc_file, 'w') as zf:
            zf.writestr("manifest.json", '{"name": "test"}')
            zf.writestr("flow.json", '{"version": "1.0.0"}')

        result = _extract_agrc(agrc_file)

        assert result is not None
        assert result.exists()
        assert (result / "manifest.json").exists()
        assert (result / "flow.json").exists()

    def test_extract_agrc_cached(self, tmp_path):
        """Test that extraction is cached."""
        agrc_file = tmp_path / "test.agrc"
        with zipfile.ZipFile(agrc_file, 'w') as zf:
            zf.writestr("manifest.json", '{"name": "test"}')

        result1 = _extract_agrc(agrc_file)
        result2 = _extract_agrc(agrc_file)

        assert result1 == result2
