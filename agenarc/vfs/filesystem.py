"""
VFS (Virtual File System)

Provides agrc:// protocol mapping for .agrc bundle assets.
Enables secure access to bundle resources without exposing filesystem.

VFS Mapping:
- agrc://prompts/  -> <bundle>/prompts/
- agrc://scripts/  -> <bundle>/scripts/
- agrc://assets/   -> <bundle>/assets/
- agrc://flow.json -> <bundle>/flow.json

Permission Model (rwx):
- Permissions are configured directly in manifest.json under permissions
- Format: {"prompts": "r--", "scripts": "rw-", "assets": "r--"}
- Subdirectories inherit parent permissions if not explicitly configured
- Default permission: "---" (no access, directory not allowed)
- Only directories with non-"---" permission are accessible
"""


from pathlib import Path
from typing import Any, Dict, Optional


class VFSError(Exception):
    """Raised for VFS-related errors."""
    pass


class VFS:
    """
    Virtual File System for .agrc bundles.

    Provides secure access to bundle assets via agrc:// protocol.

    Usage:
        vfs = VFS(bundle_path="/path/to/my_agent.agrc")
        content = vfs.read("prompts/system.pt")
        vfs.write("scripts/tool.py", "print('hello')")
    """

    # VFS scheme prefix
    VFS_SCHEME = "agrc://"

    # Default permission (no access)
    DEFAULT_PERMISSION = "---"

    def __init__(
        self,
        bundle_path: Path,
        permissions: Optional[Dict[str, str]] = None
    ):
        """
        Initialize VFS with bundle path.

        Args:
            bundle_path: Path to .agrc bundle directory
            permissions: VFS permission dict with rwx format.
                         e.g., {"prompts": "r--", "scripts": "rw-", "assets": "r--"}
                         Subdirectories inherit parent: {"prompts/custom": "rwx"}
                         Only directories with non-"---" permission are accessible.
                         If None, no permission checks are performed.
        """
        self._bundle_path = Path(bundle_path).resolve()

        # VFS permissions (rwx format)
        # If None, no permission checks are performed
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

    def _get_effective_permission(self, vfs_path: str) -> str:
        """
        Get effective permission for a VFS path.

        Args:
            vfs_path: VFS path (e.g., "prompts/subdir/file.txt")

        Returns:
            Permission string (e.g., "r--", "rw-", "rwx")
        """
        if not self._permissions:
            # No permissions configured (None or empty dict), allow all
            return "rwx"

        # Extract directory from path (e.g., "prompts/subdir" from "prompts/subdir/file.txt")
        parts = vfs_path.split("/")
        directory = parts[0] if parts else ""

        # Check explicit permission for this path (most specific)
        if vfs_path in self._permissions:
            return self._permissions[vfs_path]

        # Check explicit permission for the directory
        if directory in self._permissions:
            return self._permissions[directory]

        # Check for parent directory permissions (inheritance for subdirs)
        # e.g., for "prompts/subdir/file.txt", check "prompts"
        if directory in self._permissions:
            return self._permissions[directory]

        # Directory not configured - default to no access
        return self.DEFAULT_PERMISSION

    def _has_permission(self, vfs_path: str, operation: str) -> bool:
        """
        Check if operation is permitted for VFS path.

        Args:
            vfs_path: VFS path
            operation: "r" (read), "w" (write), "x" (execute)

        Returns:
            True if permitted
        """
        if not self._permissions:
            return True

        perm = self._get_effective_permission(vfs_path)
        return operation in perm

    def _is_directory_allowed(self, directory: str) -> bool:
        """
        Check if directory is allowed (has non-"---" permission).

        Args:
            directory: VFS directory name (prompts, scripts, assets, etc.)

        Returns:
            True if directory is accessible
        """
        if not self._permissions:
            return True

        if directory in self._permissions:
            return self._permissions[directory] != self.DEFAULT_PERMISSION

        # Not configured, default to not allowed
        return False

    def _parse_vfs_path(self, vfs_path: str) -> tuple[str, str]:
        """
        Parse VFS path into (dir, filename).

        Args:
            vfs_path: VFS path like "agrc://prompts/system.pt"

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
        if not self._is_directory_allowed(directory):
            raise VFSError(f"Directory not allowed: {directory}")

        return directory, filename

    def _get_real_path(self, vfs_path: str) -> Path:
        """
        Convert VFS path to real filesystem path.

        Args:
            vfs_path: VFS path like "agrc://prompts/system.pt"

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
            vfs_path: VFS path like "agrc://prompts/system.pt"
            encoding: File encoding (default utf-8)

        Returns:
            File content as string

        Raises:
            VFSError: If permission denied or path invalid
        """
        # Check read permission
        if not self._has_permission(vfs_path, "r"):
            raise VFSError(f"Permission denied: read not allowed for {vfs_path}")

        real_path = self._get_real_path(vfs_path)

        if not real_path.exists():
            raise VFSError(f"File not found: {vfs_path}")

        if not real_path.is_file():
            raise VFSError(f"Not a file: {vfs_path}")

        try:
            return real_path.read_text(encoding=encoding)
        except Exception as e:
            raise VFSError(f"Failed to read {vfs_path}: {e}")

    def write(self, vfs_path: str, content: str, encoding: str = "utf-8") -> None:
        """
        Write content to VFS path.

        Args:
            vfs_path: VFS path like "agrc://scripts/tool.py"
            content: Content to write
            encoding: File encoding (default utf-8)

        Raises:
            VFSError: If permission denied or path invalid
        """
        # Check write permission
        if not self._has_permission(vfs_path, "w"):
            raise VFSError(f"Permission denied: write not allowed for {vfs_path}")

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
            vfs_dir: VFS directory like "agrc://prompts"

        Returns:
            List of filenames/directories (empty if directory not allowed)
        """
        if not vfs_dir.startswith(self.VFS_SCHEME):
            vfs_dir = self.VFS_SCHEME + vfs_dir

        # Parse directory
        if not vfs_dir.endswith("/"):
            vfs_dir += "/"

        parts = vfs_dir[len(self.VFS_SCHEME):].rstrip("/").split("/")
        if not parts:
            return []

        directory = parts[0]

        # If directory not allowed, return empty (ignore silently)
        if not self._is_directory_allowed(directory):
            return []

        real_dir = self._bundle_path / directory

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


def resolve_agrc_path(vfs_path: str, bundle_path: Path) -> Optional[Path]:
    """
    Resolve agrc:// path to real filesystem path.

    Args:
        vfs_path: VFS path like "agrc://prompts/system.pt"
        bundle_path: Bundle root path

    Returns:
        Real Path or None if invalid
    """
    if not vfs_path.startswith("agrc://"):
        return None

    # Parse path
    path = vfs_path[len("agrc://"):]  # Remove "agrc://"

    # Special case for flow.json (agrc://flow.json)
    if path == "flow.json":
        return bundle_path / "flow.json"

    parts = path.split("/")

    if len(parts) < 2:
        return None

    directory = parts[0]
    filename = "/".join(parts[1:])

    # Check directory is in the standard VFS directories
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