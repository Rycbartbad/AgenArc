"""
Command: init — Interactive configuration wizard.

Guides user through provider selection, API key input, model selection,
and writes ~/.agenarc/config.yaml.
"""

import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Provider presets
PROVIDERS: dict[str, dict[str, str | None]] = {
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com"},
    "openai": {"name": "OpenAI", "base_url": "https://api.openai.com/v1"},
    "anthropic": {"name": "Anthropic", "base_url": "https://api.anthropic.com"},
    "groq": {"name": "Groq", "base_url": "https://api.groq.com/openai/v1"},
    "openrouter": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1"},
    "ollama": {"name": "Ollama", "base_url": "http://localhost:11434/v1"},
    "siliconflow": {"name": "硅基流动", "base_url": "https://api.siliconflow.cn/v1"},
    "zhipu": {"name": "智谱 ZhipuAI", "base_url": "https://open.bigmodel.cn/api/paas/v4"},
    "moonshot": {"name": "月之暗面", "base_url": "https://api.moonshot.cn/v1"},
    "dashscope": {"name": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "bytedance": {"name": "豆包", "base_url": "https://ark.cn-beijing.volces.com/api/v3"},
    "custom": {"name": "自定义", "base_url": None},
}

# Fallback models per provider (used when API call fails)
FALLBACK_MODELS: dict[str, list[str]] = {
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    "anthropic": ["claude-sonnet-4-20250514", "claude-haiku-3-5-20250514"],
    "groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    "openrouter": ["openai/gpt-4o", "anthropic/claude-sonnet-4"],
    "ollama": ["llama3", "qwen2.5"],
    "siliconflow": ["Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-V3"],
    "zhipu": ["glm-4", "glm-4-flash"],
    "moonshot": ["moonshot-v1-8k", "moonshot-v1-32k"],
    "dashscope": ["qwen-plus", "qwen-max"],
    "bytedance": ["doubao-pro-32k", "doubao-lite-32k"],
}


def _print_banner() -> None:
    """Print welcome banner."""
    print("=" * 60)
    print("  AgenArc - Interactive Configuration Wizard")
    print("=" * 60)
    print()
    print("  This wizard will help you set up AgenArc step by step.")
    print("  Press Ctrl+C at any time to exit without saving.")
    print()


def _get_input(prompt: str, default: str | None = None, allow_empty: bool = False) -> str:
    """
    Get user input with optional default value.

    Args:
        prompt: Input prompt text
        default: Default value (shown in brackets)
        allow_empty: Whether empty input is allowed

    Returns:
        User input string

    Raises:
        KeyboardInterrupt: On Ctrl+C
    """
    full_prompt = f"{prompt} [{default}]: " if default is not None else f"{prompt}: "

    try:
        value = input(full_prompt).strip()
    except EOFError:
        print()
        raise KeyboardInterrupt() from None
    except KeyboardInterrupt:
        print()
        raise

    if not value and default is not None:
        return default

    if not value and not allow_empty:
        return _get_input(prompt, default, allow_empty)

    return value


def _select_provider() -> tuple[str, str, str | None]:
    """
    Show provider selection menu.

    Returns:
        Tuple of (provider_key, provider_name, base_url)
    """
    provider_keys = list(PROVIDERS.keys())

    print()
    print("Available providers:")
    print("-" * 60)
    for i, key in enumerate(provider_keys, 1):
        info = PROVIDERS[key]
        name = info["name"]
        url = info["base_url"] or "user-defined"
        print(f"  {i:>2}. {name:20s} ({url})")
    print("-" * 60)

    while True:
        choice = _get_input("Select provider [1]")

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(provider_keys):
                key = provider_keys[idx]
                info = PROVIDERS[key]
                return key, info["name"], info["base_url"]  # type: ignore[return-value]
        except (ValueError, IndexError):
            pass

        # Check if user typed a provider key directly
        if choice.lower() in PROVIDERS:
            key = choice.lower()
            info = PROVIDERS[key]
            return key, info["name"], info["base_url"]  # type: ignore[return-value]

        print(f"  Invalid choice. Please enter a number between 1 and {len(provider_keys)}.")


def _input_api_key(provider_key: str, provider_name: str) -> str:
    """
    Prompt for API key with validation.

    Args:
        provider_key: Provider identifier
        provider_name: Display name

    Returns:
        API key string
    """
    # Don't ask for API key for Ollama (local)
    if provider_key == "ollama":
        return ""

    print()
    print(f"  {provider_name} API Key")
    print("  (will be stored in ~/.agenarc/config.yaml)")

    while True:
        key = _get_input("  Enter your API key")

        if not key:
            print("  API key cannot be empty.")
            continue

        if len(key) < 8:
            print("  API key seems too short. Please double-check.")
            continue

        return key


def _input_custom_base_url() -> str:
    """
    Ask for base URL when custom provider is selected.

    Returns:
        Base URL string
    """
    print()
    print("  Enter the API base URL for your custom provider.")
    print("  Example: https://api.example.com/v1")

    while True:
        url = _get_input("  Base URL")

        if not url:
            print("  Base URL cannot be empty.")
            continue

        if not url.startswith(("http://", "https://")):
            print("  URL must start with http:// or https://")
            continue

        return url.rstrip("/")


def _test_connection(provider_key: str, base_url: str, api_key: str) -> bool:
    """
    Test connection to provider API.

    Args:
        provider_key: Provider identifier
        base_url: API base URL
        api_key: API key (empty for Ollama)

    Returns:
        True if connection successful
    """
    print(f"  Testing connection to {base_url}... ", end="", flush=True)

    try:
        if provider_key == "anthropic":
            # Anthropic: just check reachability via HEAD
            req = urllib.request.Request(base_url, method="HEAD")
            req.add_header("x-api-key", api_key)
            req.add_header("anthropic-version", "2023-06-01")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10):
                print("OK")
                return True

        elif provider_key == "ollama":
            # Ollama: check /api/tags
            url = f"{base_url.rstrip('/v1')}/api/tags" if base_url.endswith("/v1") else f"{base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10):
                print("OK")
                return True

        else:
            # OpenAI-compatible: GET /models
            url = f"{base_url}/models"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10):
                print("OK")
                return True

    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print("FAILED")
        print(f"  Connection error: {e}")
        return False


def _fetch_models(provider_key: str, base_url: str, api_key: str) -> list[str] | None:
    """
    Fetch available models from provider API.

    Args:
        provider_key: Provider identifier
        base_url: API base URL
        api_key: API key

    Returns:
        List of model IDs, or None if fetching failed
    """
    try:
        if provider_key == "anthropic":
            # Anthropic: hardcoded list
            return ["claude-sonnet-4-20250514", "claude-haiku-3-5-20250514", "claude-opus-4-20250514"]

        elif provider_key == "ollama":
            # Ollama: GET /api/tags
            url = f"{base_url.rstrip('/v1')}/api/tags" if base_url.endswith("/v1") else f"{base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models: list[str] = []
                # Ollama returns {"models": [{"name": "llama3:latest", ...}, ...]}
                for model in data.get("models", []):
                    name = model.get("name", "")
                    if name:
                        # Strip :latest suffix
                        name = name.replace(":latest", "")
                        models.append(name)
                return models if models else None

        else:
            # OpenAI-compatible: GET /models
            url = f"{base_url}/models"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                # OpenAI format: {"data": [{"id": "gpt-4", ...}, ...]}
                raw_models: list[str] = []
                for entry in data.get("data", []):
                    model_id = entry.get("id", "")
                    if model_id:
                        raw_models.append(model_id)
                return raw_models if raw_models else None

    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return None


def _select_model(provider_key: str, models: list[str]) -> str:
    """
    Show model selection and let user pick.

    Args:
        provider_key: Provider identifier
        models: List of available model IDs

    Returns:
        Selected model ID
    """
    # Show first 20 models
    display = models[:20]
    truncated = len(models) > 20

    print()
    print("  Available models:")
    print(f"  {'-' * 56}")
    for i, model in enumerate(display, 1):
        print(f"  {i:>3}. {model}")
    if truncated:
        print(f"      ... and {len(models) - 20} more (not shown)")

    print(f"  {'-' * 56}")
    print("  Enter a number to select, or type a custom model name.")
    print(f"  [default: {display[0] if display else ''}]")

    while True:
        choice = _get_input("  Select model", default=display[0] if display else "")

        # Check if it's a number
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(display):
                return display[idx]
        except ValueError:
            pass

        # Treat as custom model name
        if choice:
            return choice

        print("  Please enter a valid number or model name.")


def _input_temperature() -> float:
    """
    Prompt for temperature setting.

    Returns:
        Temperature value (0.0 - 2.0)
    """
    print()
    print("  Temperature controls randomness (0.0 = deterministic, 2.0 = very random)")

    while True:
        val = _get_input("  Temperature", default="0.7")

        try:
            temp = float(val)
            if 0.0 <= temp <= 2.0:
                return temp
        except ValueError:
            pass

        print("  Please enter a number between 0.0 and 2.0.")


def _yaml_dump(data: dict, indent: int = 0) -> str:
    """
    Simple YAML serializer without external dependencies.

    Args:
        data: Dictionary to serialize
        indent: Current indentation level

    Returns:
        YAML string
    """
    lines: list[str] = []
    prefix = "  " * indent

    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_yaml_dump(value, indent + 1))
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        elif value is None:
            lines.append(f"{prefix}{key}: null")
        elif isinstance(value, (int, float)):
            lines.append(f"{prefix}{key}: {value}")
        else:
            # String - quote if it contains special chars
            str_val = str(value)
            if any(c in str_val for c in (":", "#", "{", "}", "[", "]", ",", "&", "*", "!", "|", ">", "'", '"')):
                lines.append(f'{prefix}{key}: "{str_val}"')
            else:
                lines.append(f"{prefix}{key}: {str_val}")

    return "\n".join(lines)


def _write_config(
    provider_key: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
) -> None:
    """
    Write configuration to ~/.agenarc/config.yaml.

    Args:
        provider_key: Provider identifier
        base_url: API base URL
        api_key: API key
        model: Default model
        temperature: Temperature value
    """
    config_dir = Path.home() / ".agenarc"
    config_path = config_dir / "config.yaml"

    # Check if config already exists
    if config_path.exists():
        print()
        overwrite = _get_input("  Config already exists. Overwrite?", default="y")
        if overwrite.lower() not in ("y", "yes"):
            print("  Configuration not written.")
            return

    # Build config dict
    config: dict[str, dict] = {
        "providers": {
            provider_key: {
                "api_key": api_key,
                "base_url": base_url,
                "default_model": model,
                "temperature": temperature,
            }
        },
        "agent": {
            "checkpoint_dir": "~/.agenarc",
        },
    }

    # Create directory
    config_dir.mkdir(parents=True, exist_ok=True)

    # Write YAML
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(_yaml_dump(config))
            f.write("\n")
        print(f"  Configuration written to {config_path}")
    except OSError as e:
        print(f"  ERROR: Failed to write config: {e}", file=sys.stderr)
        sys.exit(1)


def _offer_example_project() -> None:
    """Offer to create an example agent project."""
    print()
    create = _get_input("  Create an example agent project?", default="y")

    if create.lower() not in ("y", "yes"):
        print("  Skipping example project.")
        return

    # Find example source
    # Support PyInstaller bundled paths
    import sys

    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", "."))
        example_candidates = [
            base / "examples" / "my_first_agent.agrc",
        ]
    else:
        script_dir = Path(__file__).resolve().parent.parent.parent.parent  # agenarc/
        example_candidates = [
            script_dir / "examples" / "my_first_agent.agrc",
            Path.cwd() / "examples" / "my_first_agent.agrc",
            Path(__file__).resolve().parent.parent.parent / "examples" / "my_first_agent.agrc",
        ]

    example_src: Path | None = None
    for candidate in example_candidates:
        if candidate.exists() and candidate.is_dir():
            example_src = candidate
            break

    if example_src is None:
        print("  Example project not found. You can manually copy from the `examples/` directory.")
        return

    # Copy to ~/my_agent.agrc/
    dest = Path.home() / "my_agent.agrc"
    if dest.exists():
        print(f"  {dest} already exists. Skipping copy.")
    else:
        try:
            shutil.copytree(example_src, dest)
            print(f"  Example project created at: {dest}")
            print()
            print("  Run it with:")
            print(f'    agenarc run {dest} --input \'{{"payload":"Hello"}}\'')
        except (shutil.Error, OSError) as e:
            print(f"  Failed to copy example: {e}")


def command_init() -> int:
    """
    Interactive configuration wizard.

    Returns:
        Exit code (0 for success)
    """
    try:
        _print_banner()

        # --- Step 1: Provider selection ---
        print("[Step 1/5] Select a provider")
        provider_key, provider_name, preset_base_url = _select_provider()
        print(f"  Selected: {provider_name}")

        # --- Step 2: API key ---
        print()
        print(f"[Step 2/5] Configure {provider_name}")
        api_key = _input_api_key(provider_key, provider_name)

        # For custom provider, ask for base URL
        base_url = preset_base_url
        if provider_key == "custom":
            base_url = _input_custom_base_url()
        assert base_url is not None  # non-custom providers always have a base_url

        # --- Step 3: Test connection & fetch models ---
        print()
        print("[Step 3/5] Test connection and fetch models")

        if provider_key != "ollama":
            if not _test_connection(provider_key, base_url, api_key):
                print("  Will use fallback model list.")
        else:
            print("  Skipping connection test for Ollama (local).")

        # Fetch models
        models = _fetch_models(provider_key, base_url, api_key)

        if models:
            print(f"  Found {len(models)} model(s).")
        else:
            print("  Using fallback model list.")
            models = FALLBACK_MODELS.get(provider_key, ["gpt-4o-mini"])

        # --- Step 4: Model & temperature ---
        print()
        print("[Step 4/5] Select default model and settings")
        model = _select_model(provider_key, models)
        print(f"  Selected model: {model}")

        temperature = _input_temperature()
        print(f"  Temperature: {temperature}")

        # --- Step 5: Write config ---
        print()
        print("[Step 5/5] Save configuration")
        _write_config(provider_key, base_url, api_key, model, temperature)

        # --- Optional: Example project ---
        _offer_example_project()

        # --- Success ---
        print()
        print("=" * 60)
        print("  Configuration complete!")
        print("=" * 60)
        print()
        print("  Next steps:")
        print('    agenarc run <path-to-agent> --input \'{"payload":"Hello"}\'')
        print()
        print("  Quick start:")
        print("    agenarc --help")

    except KeyboardInterrupt:
        print()
        print()
        print("Configuration cancelled. No changes were saved.")
        return 1

    return 0
