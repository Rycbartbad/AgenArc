"""Unit tests for config.py."""

import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestConfig:
    """Tests for Config class."""

    def test_config_singleton(self):
        """Test Config singleton pattern."""
        from agenarc.config import Config, get_config

        # Reset singleton for test
        Config._instance = None

        c1 = Config.get_instance()
        c2 = Config.get_instance()
        assert c1 is c2

    def test_get_instance_creates_instance(self):
        """Test get_instance creates instance if none exists."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        instance = Config.get_instance()
        assert instance is not None
        assert isinstance(instance, Config)

    def test_config_get_with_default(self):
        """Test Config.get with default value."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {}

        assert config.get("nonexistent") is None
        assert config.get("nonexistent", "default") == "default"

    def test_config_get_nested(self):
        """Test Config.get with nested keys."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {
            "level1": {
                "level2": {
                    "value": 42
                }
            }
        }

        assert config.get("level1.level2.value") == 42

    def test_config_get_nested_missing(self):
        """Test Config.get with missing nested keys."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {"level1": {}}

        assert config.get("level1.level2.value") is None

    def test_get_openai_api_key_from_config(self):
        """Test getting OpenAI API key from config."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {"openai": {"api_key": "test-key-123"}}

        assert config.get_openai_api_key() == "test-key-123"

    def test_get_openai_api_key_from_env(self):
        """Test getting OpenAI API key from environment."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {"openai": {}}

        with patch.dict(os.environ, {"AGENARC_OPENAI_API_KEY": "env-key"}):
            config._apply_env_overrides()
            assert config.get_openai_api_key() == "env-key"

    def test_get_openai_base_url(self):
        """Test getting OpenAI base URL."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {"openai": {"base_url": "https://custom.api.com"}}

        assert config.get_openai_base_url() == "https://custom.api.com"

    def test_get_openai_model_default(self):
        """Test getting default OpenAI model."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {}

        assert config.get_openai_model() == "gpt-4"

    def test_get_openai_model_custom(self):
        """Test getting custom OpenAI model."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {"openai": {"default_model": "gpt-3.5-turbo"}}

        assert config.get_openai_model() == "gpt-3.5-turbo"

    def test_get_openai_temperature(self):
        """Test getting OpenAI temperature."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {"openai": {"default_temperature": 0.9}}

        assert config.get_openai_temperature() == 0.9

    def test_get_anthropic_api_key(self):
        """Test getting Anthropic API key."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {"anthropic": {"api_key": "anthropic-key"}}

        assert config.get_anthropic_api_key() == "anthropic-key"

    def test_get_anthropic_model_default(self):
        """Test getting default Anthropic model."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {}

        assert config.get_anthropic_model() == "claude-3-sonnet-20240229"

    def test_get_checkpoint_dir_default(self):
        """Test getting default checkpoint directory."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {}

        checkpoint_dir = config.get_checkpoint_dir()
        # On Windows, ~ expands to the user home directory
        assert ".agenarc" in str(checkpoint_dir)
        assert "checkpoints" in str(checkpoint_dir)

    def test_get_checkpoint_dir_custom(self):
        """Test getting custom checkpoint directory."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {"agent": {"checkpoint_dir": "/custom/path"}}

        assert config.get_checkpoint_dir() == Path("/custom/path")

    def test_get_storage_dir_default(self):
        """Test getting default storage directory."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {}

        storage_dir = config.get_storage_dir()
        # On Windows, ~ expands to the user home directory
        assert ".agenarc" in str(storage_dir)
        assert "storage" in str(storage_dir)

    def test_env_overrides_config(self):
        """Test environment variables override config file."""
        from agenarc.config import Config

        # Reset singleton for test
        Config._instance = None

        config = Config()
        config._config = {"openai": {"api_key": "config-key"}}

        with patch.dict(os.environ, {"AGENARC_OPENAI_API_KEY": "env-key"}):
            config._apply_env_overrides()
            assert config.get_openai_api_key() == "env-key"


class TestGetConfigFunction:
    """Tests for get_config() function."""

    def test_get_config_returns_singleton(self):
        """Test get_config returns the singleton instance."""
        from agenarc.config import Config, get_config

        # Reset singleton for test
        Config._instance = None

        config = get_config()
        assert config is get_config()
