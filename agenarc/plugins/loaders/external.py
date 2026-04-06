"""
External Plugin Loader

Loads external plugins via subprocess IPC (HTTP, gRPC, or stdio).
"""

import asyncio
import json
import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExternalPluginConfig:
    """Configuration for an external plugin."""
    protocol: str = "stdio"  # "stdio", "http", "grpc"
    command: List[str] = None  # For stdio protocol
    url: str = ""  # For http/grpc protocols
    env: Dict[str, str] = None
    startup_timeout: float = 10.0
    request_timeout: float = 30.0


class ExternalPluginLoader:
    """
    Loads external plugins via subprocess IPC.

    Plugin communication via JSON-RPC 2.0 over:
    - stdio: subprocess with JSON-RPC messages on stdin/stdout
    - http: REST API calls to running service
    - grpc: gRPC calls (future)

    agenarc.json format:
        {
            "name": "plugin_name",
            "version": "1.0.0",
            "loader": "external",
            "config": {
                "protocol": "stdio",
                "command": ["./plugin", "--mode", "agent"],
                "env": {"PLUGIN_VAR": "value"}
            }
        }
    """

    def __init__(self):
        self._processes: Dict[str, subprocess.Popen] = {}
        self._configs: Dict[str, ExternalPluginConfig] = {}
        self._lock = threading.Lock()

    async def discover(
        self,
        search_path: Path,
        callback: Callable[[Any], None]
    ) -> List[str]:
        """
        Discover external plugins in a directory.

        Args:
            search_path: Directory to search
            callback: Called with each discovered PluginInfo

        Returns:
            List of discovered plugin names
        """
        discovered = []

        if not search_path.exists():
            return discovered

        # Look for directories with agenarc.json
        for item in search_path.iterdir():
            if not item.is_dir():
                continue

            manifest_path = item / "agenarc.json"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                loader_type = manifest.get("loader", "")
                if loader_type != "external":
                    continue

                config_data = manifest.get("config", {})
                config = ExternalPluginConfig(
                    protocol=config_data.get("protocol", "stdio"),
                    command=config_data.get("command"),
                    url=config_data.get("url", ""),
                    env=config_data.get("env", {}),
                    startup_timeout=config_data.get("startup_timeout", 10.0),
                    request_timeout=config_data.get("request_timeout", 30.0),
                )

                from agenarc.plugins.hot_loader import PluginInfo

                plugin_info = PluginInfo(
                    name=manifest.get("name", item.name),
                    version=manifest.get("version", "1.0.0"),
                    path=manifest_path,
                    loader_type="external",
                )

                self._configs[manifest.get("name", item.name)] = config

                await callback(plugin_info)
                discovered.append(plugin_info.name)

            except Exception as e:
                logger.debug(f"Failed to load plugin manifest {manifest_path}: {e}")

        return discovered

    async def load(self, plugin_info: Any) -> Dict[str, Any]:
        """
        Load an external plugin and return its operators.

        Args:
            plugin_info: PluginInfo object

        Returns:
            Dict mapping operator names to ExternalOperatorWrapper instances
        """
        config = self._configs.get(plugin_info.name)
        if not config:
            logger.error(f"No config found for plugin: {plugin_info.name}")
            return {}

        operators = {}

        if config.protocol == "stdio":
            operators = await self._load_stdio_plugin(plugin_info.name, config)
        elif config.protocol == "http":
            operators = await self._load_http_plugin(plugin_info.name, config)
        elif config.protocol == "grpc":
            logger.warning("gRPC protocol not yet implemented")
            return {}
        else:
            logger.error(f"Unknown protocol: {config.protocol}")
            return {}

        return operators

    async def _load_stdio_plugin(
        self,
        plugin_name: str,
        config: ExternalPluginConfig
    ) -> Dict[str, Any]:
        """Load a stdio-based external plugin."""
        if not config.command:
            logger.error(f"No command specified for stdio plugin: {plugin_name}")
            return {}

        try:
            # Start subprocess
            env = {**os.environ, **(config.env or {})}
            process = subprocess.Popen(
                config.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
            )

            with self._lock:
                self._processes[plugin_name] = process

            # Send handshake
            handshake = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "name": plugin_name,
                    "version": "1.0.0",
                    "capabilities": ["operators", "health"],
                },
                "id": 1,
            }

            response = await self._send_stdio_request(plugin_name, handshake)
            if not response or "result" not in response:
                logger.error(f"Plugin initialization failed: {response}")
                return {}

            operators = {}
            for op_name in response.get("result", {}).get("operators", []):
                operators[op_name] = ExternalOperatorWrapper(
                    plugin_name=plugin_name,
                    operator_name=op_name,
                    loader=self,
                )

            logger.info(f"Loaded stdio plugin: {plugin_name} with {len(operators)} operators")
            return operators

        except Exception as e:
            logger.error(f"Failed to load stdio plugin {plugin_name}: {e}")
            return {}

    async def _load_http_plugin(
        self,
        plugin_name: str,
        config: ExternalPluginConfig
    ) -> Dict[str, Any]:
        """Load an HTTP-based external plugin."""
        if not config.url:
            logger.error(f"No URL specified for HTTP plugin: {plugin_name}")
            return {}

        try:
            # Health check
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{config.url}/health", timeout=5) as resp:
                    if resp.status != 200:
                        logger.error(f"Plugin health check failed: {resp.status}")
                        return {}

            # Get operator list
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{config.url}/operators") as resp:
                    data = await resp.json()

            operators = {}
            for op_name in data.get("operators", []):
                operators[op_name] = ExternalOperatorWrapper(
                    plugin_name=plugin_name,
                    operator_name=op_name,
                    loader=self,
                    base_url=config.url,
                )

            logger.info(f"Loaded HTTP plugin: {plugin_name} with {len(operators)} operators")
            return operators

        except ImportError:
            logger.error("aiohttp required for HTTP plugins: pip install aiohttp")
            return {}
        except Exception as e:
            logger.error(f"Failed to load HTTP plugin {plugin_name}: {e}")
            return {}

    async def _send_stdio_request(
        self,
        plugin_name: str,
        request: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request to a stdio plugin."""
        process = self._processes.get(plugin_name)
        if not process or process.poll() is not None:
            logger.error(f"Plugin process not running: {plugin_name}")
            return None

        try:
            # Send request
            request_json = json.dumps(request) + "\n"
            process.stdin.write(request_json)
            process.stdin.flush()

            # Read response
            response_line = await asyncio.wait_for(
                asyncio.to_thread(process.stdout.readline),
                timeout=30.0,
            )

            if not response_line:
                return None

            return json.loads(response_line)

        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for plugin response: {plugin_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to send stdio request: {e}")
            return None

    async def call_operator(
        self,
        plugin_name: str,
        operator_name: str,
        method: str,
        params: Dict[str, Any],
    ) -> Any:
        """
        Call an operator method via IPC.

        Args:
            plugin_name: Name of the plugin
            operator_name: Name of the operator
            method: Method to call
            params: Parameters

        Returns:
            Result from operator
        """
        config = self._configs.get(plugin_name)
        if not config:
            raise ValueError(f"Unknown plugin: {plugin_name}")

        if config.protocol == "stdio":
            return await self._call_stdio_operator(plugin_name, operator_name, method, params)
        elif config.protocol == "http":
            return await self._call_http_operator(plugin_name, operator_name, method, params)

    async def _call_stdio_operator(
        self,
        plugin_name: str,
        operator_name: str,
        method: str,
        params: Dict[str, Any],
    ) -> Any:
        """Call operator via stdio."""
        request = {
            "jsonrpc": "2.0",
            "method": f"{operator_name}.{method}",
            "params": params,
            "id": id(params),
        }

        response = await self._send_stdio_request(plugin_name, request)
        if not response:
            raise RuntimeError(f"Plugin call failed: {plugin_name}.{operator_name}.{method}")

        if "error" in response:
            raise RuntimeError(f"Plugin error: {response['error']}")

        return response.get("result")

    async def _call_http_operator(
        self,
        plugin_name: str,
        operator_name: str,
        method: str,
        params: Dict[str, Any],
    ) -> Any:
        """Call operator via HTTP."""
        config = self._configs.get(plugin_name)
        if not config:
            raise ValueError(f"Unknown plugin: {plugin_name}")

        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config.url}/operators/{operator_name}/{method}",
                json=params,
                timeout=aiohttp.ClientTimeout(total=config.request_timeout),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"HTTP {resp.status}: {text}")
                return await resp.json()

    def unload(self, plugin_name: str) -> bool:
        """
        Unload an external plugin.

        Args:
            plugin_name: Name of plugin to unload

        Returns:
            True if successful
        """
        with self._lock:
            if plugin_name in self._processes:
                try:
                    process = self._processes[plugin_name]
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                except Exception as e:
                    logger.error(f"Failed to stop plugin process: {e}")

                del self._processes[plugin_name]
                return True

            if plugin_name in self._configs:
                del self._configs[plugin_name]
                return True

        return False


class ExternalOperatorWrapper:
    """
    Wrapper for external plugin operators.

    Provides a transparent interface to call operators via IPC.
    """

    def __init__(
        self,
        plugin_name: str,
        operator_name: str,
        loader: ExternalPluginLoader,
        base_url: str = "",
    ):
        self.plugin_name = plugin_name
        self.operator_name = operator_name
        self._loader = loader
        self.base_url = base_url

    async def execute(self, inputs: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Execute the operator via IPC."""
        return await self._loader.call_operator(
            self.plugin_name,
            self.operator_name,
            "execute",
            {"inputs": inputs, "context": {}},
        )

    async def validate(self, inputs: Dict[str, Any]) -> bool:
        """Validate inputs via IPC."""
        try:
            result = await self._loader.call_operator(
                self.plugin_name,
                self.operator_name,
                "validate",
                {"inputs": inputs},
            )
            return bool(result)
        except Exception:
            return False

    @property
    def name(self) -> str:
        return f"{self.plugin_name}.{self.operator_name}"


# Import for os.environ
import os
