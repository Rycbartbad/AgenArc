"""Unit tests for cli/commands/init.py."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

import pytest

from agenarc.cli.commands.init import (
    FALLBACK_MODELS,
    PROVIDERS,
    _get_input,
    _input_api_key,
    _input_temperature,
    _offer_example_project,
    _select_model,
    _select_provider,
    _yaml_dump,
    command_init,
)

# =============================================================================
# _yaml_dump
# =============================================================================


class TestYamlDump:
    """Tests for _yaml_dump."""

    def test_simple_key_value(self) -> None:
        """Test simple key-value pairs."""
        result = _yaml_dump({"key": "value", "number": 42})
        assert "key: value" in result
        assert "number: 42" in result

    def test_nested_dict(self) -> None:
        """Test nested dict with indentation."""
        result = _yaml_dump({"outer": {"inner": "val", "num": 1}})
        assert "outer:" in result
        assert "  inner: val" in result
        assert "  num: 1" in result

    def test_bool_values(self) -> None:
        """Test boolean serialization."""
        result = _yaml_dump({"enabled": True, "disabled": False})
        assert "enabled: true" in result
        assert "disabled: false" in result

    def test_none_value(self) -> None:
        """Test None serialization."""
        result = _yaml_dump({"key": None})
        assert "key: null" in result

    def test_string_with_special_chars(self) -> None:
        """Test string quoting for special YAML chars."""
        result = _yaml_dump({"url": "https://example.com:8080/path"})
        assert 'url: "https://example.com:8080/path"' in result

    def test_float_value(self) -> None:
        """Test float serialization."""
        result = _yaml_dump({"temp": 0.7})
        assert "temp: 0.7" in result

    def test_int_value_zero(self) -> None:
        """Test integer zero serialization."""
        result = _yaml_dump({"count": 0})
        assert "count: 0" in result

    def test_empty_dict(self) -> None:
        """Test empty dictionary."""
        result = _yaml_dump({})
        assert result == ""

    def test_full_config_dict(self) -> None:
        """Test a realistic configuration dictionary."""
        data: dict[str, Any] = {
            "providers": {
                "deepseek": {
                    "api_key": "sk-test123",
                    "base_url": "https://api.deepseek.com",
                    "default_model": "deepseek-chat",
                    "temperature": 0.7,
                }
            },
            "agent": {
                "checkpoint_dir": "~/.agenarc",
            },
        }
        result = _yaml_dump(data)
        assert "providers:" in result
        assert "deepseek:" in result
        assert "api_key: sk-test123" in result
        assert 'base_url: "https://api.deepseek.com"' in result
        assert "default_model: deepseek-chat" in result
        assert "temperature: 0.7" in result
        assert "agent:" in result
        assert "checkpoint_dir: ~/.agenarc" in result


# =============================================================================
# _get_input
# =============================================================================


class TestGetInput:
    """Tests for _get_input."""

    def test_basic_stripped(self) -> None:
        """Test that input is stripped and returned."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "  hello  "
            result = _get_input("Enter value")
            assert result == "hello"

    def test_default_returned_on_empty(self) -> None:
        """Test that default is returned when input is empty."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = ""
            result = _get_input("Enter value", default="def_val")
            assert result == "def_val"

    def test_empty_not_allowed_reprompts(self) -> None:
        """Test that empty input reprompts when not allowed."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["", "", "final"]
            result = _get_input("Enter value", allow_empty=False)
            assert result == "final"
            assert mock_input.call_count >= 2

    def test_keyboard_interrupt_re_raised(self) -> None:
        """Test that KeyboardInterrupt is re-raised."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = KeyboardInterrupt()
            with pytest.raises(KeyboardInterrupt):
                _get_input("Enter value")

    def test_eoferror_becomes_keyboard_interrupt(self) -> None:
        """Test that EOFError is converted to KeyboardInterrupt."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = EOFError()
            with pytest.raises(KeyboardInterrupt):
                _get_input("Enter value")

    def test_prompt_format_with_default(self) -> None:
        """Test that prompts include default in brackets."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "x"
            _get_input("Name", default="Alice")
            mock_input.assert_called_once_with("Name [Alice]: ")

    def test_prompt_format_without_default(self) -> None:
        """Test that prompts without default use colon only."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "x"
            _get_input("Name")
            mock_input.assert_called_once_with("Name: ")


# =============================================================================
# PROVIDERS
# =============================================================================


class TestProviders:
    """Tests for PROVIDERS constant."""

    def test_has_twelve_providers(self) -> None:
        """Test that there are exactly 12 providers."""
        assert len(PROVIDERS) == 12

    def test_all_have_name_key(self) -> None:
        """Test every provider has a 'name' key."""
        for key, info in PROVIDERS.items():
            assert "name" in info, f"Provider {key!r} missing 'name'"

    def test_all_have_base_url_key(self) -> None:
        """Test every provider has a 'base_url' key."""
        for key, info in PROVIDERS.items():
            assert "base_url" in info, f"Provider {key!r} missing 'base_url'"

    def test_custom_base_url_is_none(self) -> None:
        """Test that 'custom' provider has null base_url."""
        assert PROVIDERS["custom"]["base_url"] is None


# =============================================================================
# FALLBACK_MODELS
# =============================================================================


class TestFallbackModels:
    """Tests for FALLBACK_MODELS constant."""

    def test_non_empty_lists(self) -> None:
        """Test every fallback model entry has a non-empty list."""
        for key, models in FALLBACK_MODELS.items():
            assert len(models) > 0, f"Provider {key!r} has empty model list"

    def test_keys_subset_of_providers(self) -> None:
        """Test all keys exist in PROVIDERS (except 'custom')."""
        for key in FALLBACK_MODELS:
            assert key in PROVIDERS, f"Fallback key {key!r} not in PROVIDERS"

    def test_custom_not_in_fallback(self) -> None:
        """Test that 'custom' is NOT in FALLBACK_MODELS."""
        assert "custom" not in FALLBACK_MODELS

    def test_model_strings_are_non_empty(self) -> None:
        """Test no empty model strings."""
        for key, models in FALLBACK_MODELS.items():
            for model in models:
                assert model, f"Provider {key!r} has empty model string"


# =============================================================================
# _select_provider
# =============================================================================


class TestSelectProvider:
    """Tests for _select_provider."""

    def test_numeric_choice_one(self) -> None:
        """Test selecting the first provider by number 1."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "1"
            key, name, base_url = _select_provider()
            assert key == "deepseek"
            assert name == "DeepSeek"
            assert base_url == "https://api.deepseek.com"

    def test_numeric_choice_last(self) -> None:
        """Test selecting the last provider (custom)."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "12"
            key, name, base_url = _select_provider()
            assert key == "custom"
            assert name == "自定义"
            assert base_url is None

    def test_direct_key_input(self) -> None:
        """Test typing a provider key directly."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["anthropic"]
            key, name, base_url = _select_provider()
            assert key == "anthropic"
            assert name == "Anthropic"
            assert base_url == "https://api.anthropic.com"

    def test_direct_key_case_insensitive(self) -> None:
        """Test case-insensitive provider key match."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["OpenAI"]
            key, name, base_url = _select_provider()
            assert key == "openai"


# =============================================================================
# _input_api_key
# =============================================================================


class TestInputApiKey:
    """Tests for _input_api_key."""

    def test_ollama_returns_empty(self) -> None:
        """Test that ollama skips API key prompt."""
        result = _input_api_key("ollama", "Ollama")
        assert result == ""

    def test_empty_key_reprompts(self) -> None:
        """Test that empty key is rejected and reprompts."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["", "valid-long-key-here"]
            result = _input_api_key("deepseek", "DeepSeek")
            assert result == "valid-long-key-here"

    def test_short_key_reprompts(self) -> None:
        """Test that too-short key is rejected."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["ab", "valid-long-key-here"]
            result = _input_api_key("deepseek", "DeepSeek")
            assert result == "valid-long-key-here"

    def test_valid_key_accepted(self) -> None:
        """Test that a valid-length key is accepted."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "sk-this-is-a-long-enough-key"
            result = _input_api_key("openai", "OpenAI")
            assert result == "sk-this-is-a-long-enough-key"


# =============================================================================
# _select_model
# =============================================================================


class TestSelectModel:
    """Tests for _select_model."""

    def test_numeric_choice(self) -> None:
        """Test selecting model by number."""
        models = ["model-alpha", "model-beta", "model-gamma"]
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "2"
            result = _select_model("test", models)
            assert result == "model-beta"

    def test_custom_name(self) -> None:
        """Test typing a custom model name."""
        models = ["model-alpha", "model-beta"]
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["my-custom-model"]
            result = _select_model("test", models)
            assert result == "my-custom-model"

    def test_default_fallback(self) -> None:
        """Test that empty input returns the default (first model)."""
        models = ["model-alpha", "model-beta"]
        with patch("builtins.input") as mock_input:
            mock_input.return_value = ""
            result = _select_model("test", models)
            assert result == "model-alpha"

    def test_empty_models_list(self) -> None:
        """Test behavior with an empty models list."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["", "custom-model"]
            result = _select_model("test", [])
            assert result == "custom-model"

    def test_truncated_display(self) -> None:
        """Test that only first 20 are shown."""
        models = [f"model-{i}" for i in range(25)]
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "21"  # beyond display range
            # Should fail numeric and end up as custom name
            result = _select_model("test", models)
            assert result == "21"


# =============================================================================
# _input_temperature
# =============================================================================


class TestInputTemperature:
    """Tests for _input_temperature."""

    def test_accepts_default(self) -> None:
        """Test that empty input returns default 0.7."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = ""
            result = _input_temperature()
            assert result == 0.7

    def test_valid_value(self) -> None:
        """Test a valid temperature value within range."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "1.5"
            result = _input_temperature()
            assert result == 1.5

    def test_zero(self) -> None:
        """Test temperature of 0.0 (lower bound)."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "0.0"
            result = _input_temperature()
            assert result == 0.0

    def test_two_point_zero(self) -> None:
        """Test temperature of 2.0 (upper bound)."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "2.0"
            result = _input_temperature()
            assert result == 2.0

    def test_out_of_range_reprompts(self) -> None:
        """Test out-of-range value reprompts."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["3.0", "0.5"]
            result = _input_temperature()
            assert result == 0.5

    def test_negative_reprompts(self) -> None:
        """Test negative value reprompts."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["-1.0", "0.5"]
            result = _input_temperature()
            assert result == 0.5

    def test_invalid_string_reprompts(self) -> None:
        """Test non-numeric string reprompts."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["hot", "0.5"]
            result = _input_temperature()
            assert result == 0.5


# =============================================================================
# _offer_example_project
# =============================================================================


class TestOfferExampleProject:
    """Tests for _offer_example_project."""

    # The example directory exists at D:\AgenArc\examples\my_first_agent.agrc
    # so _offer_example_project will find it naturally. We only need to mock
    # Path.home() to avoid writes to the real home, and shutil.copytree to
    # avoid actual filesystem copy.

    @patch("agenarc.cli.commands.init.shutil.copytree")
    @patch("pathlib.Path.home")
    @patch("builtins.input")
    def test_input_y_creates_project(
        self, mock_input: MagicMock, mock_home: MagicMock, mock_copytree: MagicMock
    ) -> None:
        """Test that 'y' input triggers example project creation."""
        mock_input.return_value = "y"
        mock_home.return_value = Path("C:\\fake\\home")

        _offer_example_project()

        mock_copytree.assert_called_once()
        # Destination should be ~/my_agent.agrc
        args, _ = mock_copytree.call_args
        dest = args[1]
        assert "my_agent.agrc" in str(dest)

    @patch("agenarc.cli.commands.init.shutil.copytree")
    @patch("builtins.input")
    def test_input_n_skips(self, mock_input: MagicMock, mock_copytree: MagicMock) -> None:
        """Test that 'n' input skips example project creation."""
        mock_input.return_value = "n"
        _offer_example_project()
        mock_copytree.assert_not_called()

    @patch("agenarc.cli.commands.init.shutil.copytree")
    @patch("builtins.input")
    def test_input_yes_creates(self, mock_input: MagicMock, mock_copytree: MagicMock) -> None:
        """Test that 'yes' also triggers project creation."""
        mock_input.return_value = "yes"
        # Need to mock home to avoid filesystem operations
        with patch("pathlib.Path.home", return_value=Path("C:\\fake\\home")):
            _offer_example_project()
            mock_copytree.assert_called_once()

    @patch("agenarc.cli.commands.init.shutil.copytree")
    @patch("pathlib.Path.home")
    @patch("builtins.input")
    def test_default_y_creates(self, mock_input: MagicMock, mock_home: MagicMock, mock_copytree: MagicMock) -> None:
        """Test that default (empty input) also creates project."""
        mock_input.return_value = ""
        mock_home.return_value = Path("C:\\fake\\home")
        # _get_input returns default "y" when empty
        _offer_example_project()
        mock_copytree.assert_called_once()

    @patch("pathlib.Path.home")
    @patch("builtins.input")
    def test_respects_existing_destination(self, mock_input: MagicMock, mock_home: MagicMock) -> None:
        """Test that existing destination skips copy."""
        mock_input.return_value = "y"
        mock_home.return_value = Path("C:\\fake\\home")

        # Make dest.exists() return True so copy is skipped
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("agenarc.cli.commands.init.shutil.copytree") as mock_copytree:
                _offer_example_project()
                mock_copytree.assert_not_called()


# =============================================================================
# command_init — full flow
# =============================================================================


class TestCommandInit:
    """Tests for command_init."""

    @patch("agenarc.cli.commands.init._offer_example_project")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    @patch("agenarc.cli.commands.init.urllib.request.urlopen")
    @patch("builtins.input")
    def test_full_flow(
        self,
        mock_input: MagicMock,
        mock_urlopen: MagicMock,
        mock_home: MagicMock,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_open_file: MagicMock,
        mock_offer: MagicMock,
    ) -> None:
        """Test complete init flow with mocked IO."""
        mock_home.return_value = Path("C:\\fake\\home")
        mock_exists.return_value = False  # config doesn't exist yet
        mock_offer.return_value = None

        # Mock urlopen for both _test_connection and _fetch_models
        response_data = json.dumps({"data": [{"id": "deepseek-chat"}, {"id": "deepseek-reasoner"}]}).encode("utf-8")
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = response_data
        mock_urlopen.return_value = mock_response

        # Input sequence: provider 1, API key, model 1, temperature, skip example
        mock_input.side_effect = [
            "1",  # Select DeepSeek
            "sk-test-key-12345",  # API key
            "1",  # Select first model (deepseek-chat)
            "0.7",  # Temperature
            "n",  # No example project
        ]

        result = command_init()

        assert result == 0
        # Verify config was written
        mock_open_file.assert_called_once()
        # Verify the config directory was created
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("agenarc.cli.commands.init._offer_example_project")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    @patch("agenarc.cli.commands.init.urllib.request.urlopen")
    @patch("builtins.input")
    def test_full_flow_with_ollama(
        self,
        mock_input: MagicMock,
        mock_urlopen: MagicMock,
        mock_home: MagicMock,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_open_file: MagicMock,
        mock_offer: MagicMock,
    ) -> None:
        """Test complete init flow with ollama (no API key, skip connection test)."""
        mock_home.return_value = Path("C:\\fake\\home")
        mock_exists.return_value = False
        mock_offer.return_value = None

        # Mock urlopen for _fetch_models (ollama: GET /api/tags)
        response_data = json.dumps(
            {
                "models": [
                    {"name": "llama3:latest"},
                    {"name": "qwen2.5:latest"},
                ]
            }
        ).encode("utf-8")
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = response_data
        mock_urlopen.return_value = mock_response

        # Input for ollama (provider 6)
        mock_input.side_effect = [
            "6",  # Select Ollama (6th provider)
            "1",  # Select first model (llama3)
            "0.7",  # Temperature
            "n",  # No example project
        ]

        result = command_init()

        assert result == 0
        mock_open_file.assert_called_once()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    @patch("builtins.input")
    def test_ctrl_c_returns_one(
        self,
        mock_input: MagicMock,
        mock_home: MagicMock,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_open_file: MagicMock,
    ) -> None:
        """Test that KeyboardInterrupt returns exit code 1."""
        mock_home.return_value = Path("C:\\fake\\home")
        mock_exists.return_value = False

        # Raise KeyboardInterrupt on first input call
        mock_input.side_effect = KeyboardInterrupt()

        result = command_init()
        assert result == 1

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    @patch("builtins.input")
    def test_ctrl_c_during_api_key(
        self,
        mock_input: MagicMock,
        mock_home: MagicMock,
        mock_exists: MagicMock,
        mock_mkdir: MagicMock,
        mock_open_file: MagicMock,
    ) -> None:
        """Test Ctrl+C during API key input."""
        mock_home.return_value = Path("C:\\fake\\home")
        mock_exists.return_value = False

        # Provider selection works, then API key raises KeyboardInterrupt
        mock_input.side_effect = [
            "1",  # Select DeepSeek
            KeyboardInterrupt(),  # Ctrl+C during API key prompt
        ]

        result = command_init()
        assert result == 1

    def test_connection_failure_uses_fallback(self) -> None:
        """Test that connection failure falls back gracefully."""
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = [
                "1",  # Select DeepSeek
                "sk-test-key-12345",  # API key
                "1",  # Select first model
                "0.7",  # Temperature
                "n",  # No example project
            ]
            with (
                patch("pathlib.Path.home", return_value=Path("C:\\fake\\home")),
                patch("pathlib.Path.exists", return_value=False),
                patch("pathlib.Path.mkdir"),
                patch("builtins.open", new_callable=mock_open),
                patch(
                    "agenarc.cli.commands.init.urllib.request.urlopen",
                    side_effect=ConnectionError("No route to host"),
                ),
            ):
                result = command_init()
                # Should still complete with fallback models
                assert result == 0

    def test_model_fetch_failure_uses_fallback(self) -> None:
        """Test that model fetch failure uses fallback model list."""
        # Mock urlopen to succeed for connection test but fail for model fetch
        success_response = MagicMock()
        success_response.__enter__.return_value = MagicMock()

        with patch("builtins.input") as mock_input:
            mock_input.side_effect = [
                "1",  # Select DeepSeek
                "sk-test-key-12345",  # API key
                "1",  # Select first model (from fallback)
                "0.7",  # Temperature
                "n",  # No example project
            ]
            with (
                patch("pathlib.Path.home", return_value=Path("C:\\fake\\home")),
                patch("pathlib.Path.exists", return_value=False),
                patch("pathlib.Path.mkdir"),
                patch("builtins.open", new_callable=mock_open),
                patch(
                    "agenarc.cli.commands.init.urllib.request.urlopen",
                    side_effect=[success_response, OSError("Connection failed")],
                ),
                patch(
                    "agenarc.cli.commands.init._offer_example_project",
                ),
            ):
                result = command_init()
                assert result == 0

    def test_offer_example_called_in_flow(self) -> None:
        """Test that _offer_example_project is called in the flow."""
        response_data = json.dumps(
            {
                "models": [
                    {"name": "llama3:latest"},
                    {"name": "qwen2.5:latest"},
                ]
            }
        ).encode("utf-8")
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = response_data

        with patch("builtins.input") as mock_input:
            mock_input.side_effect = [
                "6",  # Select Ollama
                "1",  # Select first model
                "0.7",  # Temperature
                "n",  # No example project
            ]
            with (
                patch("pathlib.Path.home", return_value=Path("C:\\fake\\home")),
                patch("pathlib.Path.exists", return_value=False),
                patch("pathlib.Path.mkdir"),
                patch("builtins.open", new_callable=mock_open),
                patch(
                    "agenarc.cli.commands.init.urllib.request.urlopen",
                    return_value=mock_response,
                ),
                patch("agenarc.cli.commands.init._offer_example_project") as mock_offer,
            ):
                result = command_init()
                assert result == 0
                mock_offer.assert_called_once()
