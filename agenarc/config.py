"""
Configuration Management

Loads configuration from config.yaml and environment variables.
API keys take precedence over config file values.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class Config:
    """
    Configuration manager for AgenArc.

    Loads from:
    1. config.yaml in project root (if exists)
    2. Environment variables (take precedence)

    Environment variable pattern:
    - AGENARC_OPENAI_API_KEY
    - AGENARC_ANTHROPIC_API_KEY
    - AGENARC_OPENAI_MODEL
    - etc.
    """

    _instance: Optional["Config"] = None

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._load_config()

    @classmethod
    def get_instance(cls) -> "Config":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance

    def _load_config(self) -> None:
        """Load configuration from file and environment."""
        # Try to load from config.yaml
        config_path = self._find_config_file()
        if config_path and YAML_AVAILABLE:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception:
                self._config = {}

        # Environment variables override config file
        self._apply_env_overrides()

    def _find_config_file(self) -> Optional[Path]:
        """Find config.yaml in ~/.agenarc/ or project root."""
        # ~/.agenarc/config.yaml (preferred, user-level)
        user_config = Path("~/.agenarc/config.yaml").expanduser()
        if user_config.exists():
            return user_config

        # config.yaml in project root (legacy)
        current = Path(__file__).parent.parent
        config_path = current / "config.yaml"
        if config_path.exists():
            return config_path

        return None

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        # OpenAI
        if os.environ.get("AGENARC_OPENAI_API_KEY"):
            self._config.setdefault("openai", {})["api_key"] = os.environ["AGENARC_OPENAI_API_KEY"]
        if os.environ.get("AGENARC_OPENAI_BASE_URL"):
            self._config.setdefault("openai", {})["base_url"] = os.environ["AGENARC_OPENAI_BASE_URL"]
        if os.environ.get("AGENARC_OPENAI_MODEL"):
            self._config.setdefault("openai", {})["default_model"] = os.environ["AGENARC_OPENAI_MODEL"]

        # Anthropic
        if os.environ.get("AGENARC_ANTHROPIC_API_KEY"):
            self._config.setdefault("anthropic", {})["api_key"] = os.environ["AGENARC_ANTHROPIC_API_KEY"]
        if os.environ.get("AGENARC_ANTHROPIC_MODEL"):
            self._config.setdefault("anthropic", {})["default_model"] = os.environ["AGENARC_ANTHROPIC_MODEL"]

        # General
        if os.environ.get("AGENARC_CHECKPOINT_DIR"):
            self._config.setdefault("agent", {})["checkpoint_dir"] = os.environ["AGENARC_CHECKPOINT_DIR"]

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Args:
            key: Dot-notation key, e.g., "openai.api_key"
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key."""
        return self.get("openai.api_key") or os.environ.get("OPENAI_API_KEY")

    def get_openai_base_url(self) -> Optional[str]:
        """Get OpenAI base URL."""
        return self.get("openai.base_url") or os.environ.get("OPENAI_BASE_URL")

    def get_openai_model(self) -> str:
        """Get default OpenAI model."""
        return self.get("openai.default_model", "gpt-4")

    def get_openai_temperature(self) -> float:
        """Get default OpenAI temperature."""
        return float(self.get("openai.default_temperature", 0.7))

    def get_anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API key."""
        return self.get("anthropic.api_key") or os.environ.get("ANTHROPIC_API_KEY")

    def get_anthropic_model(self) -> str:
        """Get default Anthropic model."""
        return self.get("anthropic.default_model", "claude-3-sonnet-20240229")

    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get configuration for a specific provider.

        Args:
            provider: Provider name (e.g., "deepseek", "openrouter", "anthropic")

        Returns:
            Dict with api_key, base_url, and default_model
        """
        # First check top-level provider config
        provider_config = self.get(f"providers.{provider}", {})
        if provider_config:
            return {
                "api_key": provider_config.get("api_key"),
                "base_url": provider_config.get("base_url"),
                "default_model": provider_config.get("default_model") or provider_config.get("models", [""])[0] if provider_config.get("models") else "",
            }

        # Fallback to legacy top-level config
        legacy_config = self.get(provider, {})
        if legacy_config:
            return {
                "api_key": legacy_config.get("api_key"),
                "base_url": legacy_config.get("base_url"),
                "default_model": legacy_config.get("default_model"),
            }

        return {"api_key": None, "base_url": None, "default_model": None}

    def get_default_provider(self) -> str:
        """Get default provider name."""
        return self.get("default_provider", "openai")

    def get_checkpoint_dir(self) -> Path:
        """Get checkpoint directory."""
        path = self.get("agent.checkpoint_dir", "~/.agenarc/checkpoints")
        return Path(path).expanduser()

    def get_storage_dir(self) -> Path:
        """Get storage directory."""
        path = self.get("agent.storage_dir", "~/.agenarc/storage")
        return Path(path).expanduser()


def get_config() -> Config:
    """Get configuration singleton."""
    return Config.get_instance()
