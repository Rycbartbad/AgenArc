"""
VFS (Virtual File System)

Provides arc:// protocol mapping for .arc bundle assets.
Enables secure access to bundle resources without exposing filesystem.

VFS Mapping:
- arc://prompts/  -> <bundle>/prompts/
- arc://scripts/  -> <bundle>/scripts/
- arc://assets/   -> <bundle>/assets/
- arc://flow.json -> <bundle>/flow.json
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Set


class VFSError(Exception):
    """Raised for VFS-related errors."""
    pass


class VFS:
    """
    Virtual File System for .arc bundles.

    Provides secure access to bundle assets via arc:// protocol.

    Usage:
        vfs = VFS(bundle_path="/path/to/my_agent.arc")
        content = vfs.read("prompts/system.pt")
        vfs.write("scripts/tool.py", "print('hello')")
    """

    # Allowed VFS paths and their real equivalents
    VFS_SCHEME = "arc://"

    # Allowed directories within bundle
    ALLOWED_DIRS = {"prompts", "scripts", "assets"}

    def __init__(self, bundle_path: Path, permissions: Dict[str, bool] = None):
        """
        Initialize VFS with bundle path.

        Args:
            bundle_path: Path to .arc bundle directory
            permissions: Optional permissions dict from manifest.json
                         e.g., {"allow_script_read": True, "allow_prompt_write": False}
                         If None, no permission checks are performed (backward compatible).
        """
        self._bundle_path = Path(bundle_path).resolve()

        # Permissions - if None, no checks are performed
        self._permissions = permissions

        # Validate bundle exists and is a directory
        if not self._bundle_path.exists():
            raise VFSError(f"Bundle not found: {self._bundle_path}")

        if not self._bundle_path.is_dir():
            raise VFSError(f"Bundle must be a directory: {self._bundle_path}")

    @property
    def bundle_path(self) -> Path:
        """Get bundle path."""
        return self._bundle_path

    def _parse_vfs_path(self, vfs_path: str) -> tuple[str, str]:
        """
        Parse VFS path into (dir, filename).

        Args:
            vfs_path: VFS path like "arc://prompts/system.pt"

        Returns:
            Tuple of (directory, filename)
        """
        if not vfs_path.startswith(self.VFS_SCHEME):
            raise VFSError(f"Invalid VFS path: must start with {self.VFS_SCHEME}")

        # Remove scheme
        path = vfs_path[len(self.VFS_SCHEME):]

        # Split into directory and filename
        parts = path.split("/")

        if len(parts) < 2:
            raise VFSError(f"Invalid VFS path: {vfs_path}")

        directory = parts[0]
        filename = "/".join(parts[1:])

        # Validate directory is allowed
        if directory not in self.ALLOWED_DIRS:
            raise VFSError(
                f"Directory not allowed: {directory}. "
                f"Allowed: {self.ALLOWED_DIRS}"
            )

        return directory, filename

    def _get_real_path(self, vfs_path: str) -> Path:
        """
        Convert VFS path to real filesystem path.

        Args:
            vfs_path: VFS path like "arc://prompts/system.pt"

        Returns:
            Real Path object
        """
        directory, filename = self._parse_vfs_path(vfs_path)

        # Build real path
        real_path = self._bundle_path / directory / filename

        # Security check: ensure resolved path is within bundle
        resolved = real_path.resolve()
        if not resolved.is_relative_to(self._bundle_path):
            raise VFSError(
                f"Path traversal detected: {vfs_path}"
            )

        return real_path

    def read(self, vfs_path: str, encoding: str = "utf-8") -> str:
        """
        Read content from VFS path.

        Args:
            vfs_path: VFS path like "arc://prompts/system.pt"
            encoding: File encoding (default utf-8)

        Returns:
            File content as string

        Raises:
            VFSError: If permission denied or path invalid
        """
        directory, _ = self._parse_vfs_path(vfs_path)

        # Check read permission
        self._check_permission(directory, "read")

        real_path = self._get_real_path(vfs_path)

        if not real_path.exists():
            raise VFSError(f"File not found: {vfs_path}")

        if not real_path.is_file():
            raise VFSError(f"Not a file: {vfs_path}")

        try:
            return real_path.read_text(encoding=encoding)
        except Exception as e:
            raise VFSError(f"Failed to read {vfs_path}: {e}")

    def _check_permission(self, directory: str, operation: str) -> None:
        """
        Check if operation is permitted based on manifest permissions.

        Args:
            directory: VFS directory (prompts, scripts, assets)
            operation: "read" or "write"

        Raises:
            VFSError: If permission denied
        """
        # If no permissions configured (None or empty dict), skip checks
        if not self._permissions:
            return

        if operation == "read":
            if directory == "scripts" and not self._permissions.get("allow_script_read", False):
                raise VFSError(f"Permission denied: script read not allowed")
            if directory == "prompts" and not self._permissions.get("allow_prompt_read", False):
                raise VFSError(f"Permission denied: prompt read not allowed")
        elif operation == "write":
            if directory == "scripts" and not self._permissions.get("allow_script_write", False):
                raise VFSError(f"Permission denied: script write not allowed")
            if directory == "prompts" and not self._permissions.get("allow_prompt_write", False):
                raise VFSError(f"Permission denied: prompt write not allowed")

    def write(self, vfs_path: str, content: str, encoding: str = "utf-8") -> None:
        """
        Write content to VFS path.

        Args:
            vfs_path: VFS path like "arc://scripts/tool.py"
            content: Content to write
            encoding: File encoding (default utf-8)

        Raises:
            VFSError: If permission denied or path invalid
        """
        directory, _ = self._parse_vfs_path(vfs_path)

        # Check write permission
        self._check_permission(directory, "write")

        real_path = self._get_real_path(vfs_path)

        # Security check: ensure we're not writing outside bundle
        resolved = real_path.resolve()
        if not resolved.is_relative_to(self._bundle_path):
            raise VFSError(
                f"Path traversal detected: {vfs_path}"
            )

        try:
            # Ensure parent directory exists
            real_path.parent.mkdir(parents=True, exist_ok=True)

            # Write atomically (write to temp, then rename)
            tmp_path = real_path.with_suffix(real_path.suffix + ".tmp")
            tmp_path.write_text(content, encoding=encoding)
            tmp_path.replace(real_path)
        except Exception as e:
            raise VFSError(f"Failed to write {vfs_path}: {e}")

    def exists(self, vfs_path: str) -> bool:
        """
        Check if VFS path exists.

        Args:
            vfs_path: VFS path to check

        Returns:
            True if exists
        """
        try:
            real_path = self._get_real_path(vfs_path)
            return real_path.exists()
        except VFSError:
            return False

    def list_dir(self, vfs_dir: str) -> list[str]:
        """
        List contents of VFS directory.

        Args:
            vfs_dir: VFS directory like "arc://prompts"

        Returns:
            List of filenames/directories
        """
        if not vfs_dir.startswith(self.VFS_SCHEME):
            vfs_dir = self.VFS_SCHEME + vfs_dir

        # Parse directory
        if not vfs_dir.endswith("/"):
            vfs_dir += "/"

        parts = vfs_dir[len(self.VFS_SCHEME):].rstrip("/").split("/")
        if not parts or parts[0] not in self.ALLOWED_DIRS:
            raise VFSError(f"Invalid directory: {vfs_dir}")

        real_dir = self._bundle_path / parts[0]

        if not real_dir.exists():
            return []

        return [p.name for p in real_dir.iterdir()]

    def render_template(self, vfs_path: str, context: Dict[str, Any]) -> str:
        """
        Render template with context variables.

        Supports {{variable}} syntax.

        Args:
            vfs_path: VFS path to template
            context: Template variables

        Returns:
            Rendered template string
        """
        content = self.read(vfs_path)

        # Simple template rendering
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, str(value))

        return content


def resolve_arc_path(vfs_path: str, bundle_path: Path) -> Optional[Path]:
    """
    Resolve arc:// path to real filesystem path.

    Args:
        vfs_path: VFS path like "arc://prompts/system.pt"
        bundle_path: Bundle root path

    Returns:
        Real Path or None if invalid
    """
    if not vfs_path.startswith("arc://"):
        return None

    # Parse path
    path = vfs_path[6:]  # Remove "arc://"

    # Special case for flow.json (arc://flow.json)
    if path == "flow.json":
        return bundle_path / "flow.json"

    parts = path.split("/")

    if len(parts) < 2:
        return None

    directory = parts[0]
    filename = "/".join(parts[1:])

    if directory not in {"prompts", "scripts", "assets"}:
        return None

    real_path = bundle_path / directory / filename

    # Security check
    try:
        resolved = real_path.resolve()
        if not resolved.is_relative_to(bundle_path.resolve()):
            return None
        return real_path
    except Exception:
        return None
