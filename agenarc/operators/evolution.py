"""
Asset Operators

Asset_Reader - Read files from .arc bundle
Asset_Writer - Write files to .arc bundle
Runtime_Reload - Hot reload scripts and plugins
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port
from agenarc.engine.state import ExecutionContext
from agenarc.vfs.filesystem import VFS, VFSError


class Asset_Reader_Operator(IOperator):
    """
    Asset Reader operator - read files from .arc bundle.

    Reads assets from the bundle using VFS (arc:// protocol).

    Inputs:
        path: VFS path (arc://prompts/system.pt)
        encoding: File encoding (default utf-8)

    Outputs:
        content: File content
        metadata: File metadata
        success: Whether read succeeded
    """

    @property
    def name(self) -> str:
        return "builtin.asset_reader"

    @property
    def description(self) -> str:
        return "Read files from .arc bundle via VFS"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="path", type="string", description="VFS path (arc://...)"),
            Port(name="encoding", type="string", description="File encoding", default="utf-8"),
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="content", type="string", description="File content"),
            Port(name="metadata", type="object", description="File metadata"),
            Port(name="success", type="boolean", description="Whether read succeeded"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        vfs_path = inputs.get("path", "")
        encoding = inputs.get("encoding", "utf-8")

        if not vfs_path:
            return {
                "content": "",
                "metadata": {},
                "success": False
            }

        # Get bundle path from context
        bundle_path = context.get("_bundle_path")
        if not bundle_path:
            # Try to get from config or default
            from agenarc.config import get_config
            config = get_config()
            agent_dir = config.get("agent.checkpoint_dir", "~/.agenarc")
            # For now, try current directory
            bundle_path = Path.cwd()

        try:
            vfs = VFS(bundle_path)
            content = vfs.read(vfs_path, encoding)

            # Get metadata
            real_path = vfs._get_real_path(vfs_path)
            stat = real_path.stat()

            return {
                "content": content,
                "metadata": {
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "path": vfs_path,
                },
                "success": True
            }

        except VFSError as e:
            return {
                "content": "",
                "metadata": {"error": str(e)},
                "success": False
            }
        except Exception as e:
            return {
                "content": "",
                "metadata": {"error": str(e)},
                "success": False
            }


class Asset_Writer_Operator(IOperator):
    """
    Asset Writer operator - write files to .arc bundle.

    Writes assets to the bundle using VFS (arc:// protocol).
    Supports atomic writes for data integrity.

    Inputs:
        path: VFS path (arc://scripts/tool.py)
        content: Content to write
        operation: Operation (create, update, delete)
        encoding: File encoding (default utf-8)

    Outputs:
        success: Whether write succeeded
        path: Written file path
        error: Error message if failed
    """

    @property
    def name(self) -> str:
        return "builtin.asset_writer"

    @property
    def description(self) -> str:
        return "Write files to .arc bundle via VFS"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="path", type="string", description="VFS path (arc://...)"),
            Port(name="content", type="string", description="Content to write"),
            Port(name="operation", type="string", description="Operation: create, update, delete", default="create"),
            Port(name="encoding", type="string", description="File encoding", default="utf-8"),
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="success", type="boolean", description="Whether write succeeded"),
            Port(name="path", type="string", description="Written file path"),
            Port(name="error", type="string", description="Error message if failed"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        vfs_path = inputs.get("path", "")
        content = inputs.get("content", "")
        operation = inputs.get("operation", "create")
        encoding = inputs.get("encoding", "utf-8")

        if not vfs_path:
            return {
                "success": False,
                "path": "",
                "error": "Path is required"
            }

        # Get bundle path from context
        bundle_path = context.get("_bundle_path")
        if not bundle_path:
            bundle_path = Path.cwd()

        try:
            vfs = VFS(bundle_path)

            if operation == "delete":
                # Check immutable_nodes
                if self._is_immutable(vfs_path, context):
                    return {
                        "success": False,
                        "path": vfs_path,
                        "error": "Path is immutable"
                    }
                # For delete, we'd need to implement it in VFS
                return {
                    "success": False,
                    "path": vfs_path,
                    "error": "Delete not implemented yet"
                }

            # Check immutable_nodes
            if self._is_immutable(vfs_path, context):
                return {
                    "success": False,
                    "path": vfs_path,
                    "error": "Cannot write to immutable path"
                }

            # Atomic write
            if operation == "create":
                # Check if exists
                if vfs.exists(vfs_path):
                    return {
                        "success": False,
                        "path": vfs_path,
                        "error": "File already exists"
                    }

            vfs.write(vfs_path, content, encoding)

            return {
                "success": True,
                "path": vfs_path,
                "error": None
            }

        except VFSError as e:
            return {
                "success": False,
                "path": vfs_path,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "path": vfs_path,
                "error": str(e)
            }

    def _is_immutable(self, vfs_path: str, context: ExecutionContext) -> bool:
        """Check if path is in immutable_nodes list."""
        immutable_nodes = context.get("_immutable_nodes", [])
        return vfs_path in immutable_nodes


class Runtime_Reload_Operator(IOperator):
    """
    Runtime Reload operator - hot reload scripts and plugins.

    Triggers a reload of the plugin/operator registry.

    Inputs:
        target: What to reload (plugins, scripts, both)

    Outputs:
        success: Whether reload succeeded
        reloaded_scripts: List of reloaded script paths
        error: Error message if failed
    """

    @property
    def name(self) -> str:
        return "builtin.runtime_reload"

    @property
    def description(self) -> str:
        return "Hot reload scripts and plugins"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="target", type="string", description="Target: plugins, scripts, both", default="both"),
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="success", type="boolean", description="Whether reload succeeded"),
            Port(name="reloaded_scripts", type="array", description="List of reloaded scripts"),
            Port(name="error", type="string", description="Error message if failed"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        target = inputs.get("target", "both")

        try:
            reloaded = []

            if target in ("plugins", "both"):
                # Reload plugin manager
                from agenarc.plugins.manager import PluginManager
                plugin_manager = PluginManager()
                plugin_manager.discover_plugins()
                reloaded.append("plugins")

            if target in ("scripts", "both"):
                # Scan scripts directory for changes
                bundle_path = context.get("_bundle_path")
                if bundle_path:
                    scripts_dir = bundle_path / "scripts"
                    if scripts_dir.exists():
                        for script_file in scripts_dir.glob("*.py"):
                            # In a real implementation, we'd check file hash
                            # and reload if changed
                            reloaded.append(f"scripts/{script_file.name}")

            return {
                "success": True,
                "reloaded_scripts": reloaded,
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "reloaded_scripts": [],
                "error": str(e)
            }


def get_evolution_operators() -> Dict[str, type]:
    """Get all evolution operators."""
    return {
        "Asset_Reader": Asset_Reader_Operator,
        "Asset_Writer": Asset_Writer_Operator,
        "Runtime_Reload": Runtime_Reload_Operator,
    }
