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

    Permission Model:
        When permissions=None (default), all operations are allowed BUT
        path traversal protection (is_relative_to check) remains active.

        When permissions dict is provided, only explicitly allowed directories
        are accessible. Subdirectories inherit parent permissions.

    Usage:
        vfs = VFS(bundle_path="/path/to/my_agent.agrc")
        content = vfs.read("prompts/system.pt")
        vfs.write("scripts/tool.py", "print('hello')")

    Context Manager:
        Supports 'with VFS(path) as vfs:' pattern.

    Raises:
        VFSError: For permission denied, path traversal, or invalid operations
    """

    # VFS scheme prefix
    VFS_SCHEME = "agrc://"

    # Default permission (no access)
    DEFAULT_PERMISSION = "---"

    # Permission constants
    PERM_ALL = "rwx"
    PERM_READ = "r"
    PERM_WRITE = "w"
    PERM_EXEC = "x"

    # File size limits
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_TEMPLATE_SIZE = 1024 * 1024  # 1MB

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
        if self._permissions:
            # Normalize: strip trailing slashes from keys
            self._permissions = {k.rstrip("/"): v for k, v in self._permissions.items()}

        # Permission cache for performance
        self._permission_cache: Dict[str, str] = {}

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
        Get effective permission for a VFS path with hierarchical inheritance.

        Check order: exact path match -> parent directory inheritance ->
        top-level directory -> default

        Args:
            vfs_path: VFS path (e.g., "prompts/subdir/file.txt")

        Returns:
            Permission string (e.g., "r--", "rw-", "rwx")
        """
        if not self._permissions:
            # No permissions configured (None or empty dict), allow all
            return "rwx"

        # Check cache first
        if vfs_path in self._permission_cache:
            return self._permission_cache[vfs_path]

        # Normalize: strip trailing slashes
        path = vfs_path.strip("/")
        if not path:
            result = "rwx"
            self._permission_cache[vfs_path] = result
            return result

        # 1. Exact path match
        if path in self._permissions:
            result = self._permissions[path]
            self._permission_cache[vfs_path] = result
            return result

        parts = path.split("/")

        # 2. Parent directory inheritance (walk up the tree)
        # e.g., for "prompts/subdir/file.txt", check "prompts/subdir" then "prompts"
        for i in range(len(parts) - 1, 0, -1):
            parent = "/".join(parts[:i])
            if parent in self._permissions:
                result = self._permissions[parent]
                self._permission_cache[vfs_path] = result
                return result

        # 3. Top-level directory
        if parts[0] in self._permissions:
            result = self._permissions[parts[0]]
            self._permission_cache[vfs_path] = result
            return result

        # Not configured - default to no access
        result = self.DEFAULT_PERMISSION
        self._permission_cache[vfs_path] = result
        return result

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

    def _validate_filename(self, filename: str) -> None:
        """
        Validate filename has no path traversal or illegal characters.

        Args:
            filename: Filename to validate

        Raises:
            VFSError: If filename contains illegal characters
        """
        if not filename:
            return
        if filename in (".", ".."):
            raise VFSError("Invalid filename")
        illegal = set('/\\\0')
        if any(c in illegal for c in filename):
            raise VFSError("Filename contains illegal characters")

    def _get_real_path(self, vfs_path: str) -> Path:
        """
        Convert VFS path to real filesystem path.

        Args:
            vfs_path: VFS path like "agrc://prompts/system.pt"

        Returns:
            Real Path object
        """
        directory, filename = self._parse_vfs_path(vfs_path)

        # Validate filename BEFORE building path
        self._validate_filename(filename)

        # Build real path
        real_path = self._bundle_path / directory / filename

        # Security check: ensure resolved path is within bundle
        resolved = real_path.resolve()
        if not resolved.is_relative_to(self._bundle_path):
            raise VFSError("Path traversal detected")

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

    def write(self, vfs_path: str, content: str = "", encoding: str = "utf-8") -> None:
        """
        Write content to VFS path.

        Args:
            vfs_path: VFS path like "agrc://scripts/tool.py"
            content: Content to write
            encoding: File encoding (default utf-8)

        Raises:
            VFSError: If permission denied, path invalid, or content too large
        """
        # Check write permission
        if not self._has_permission(vfs_path, "w"):
            raise VFSError("Permission denied")

        # Check file size limit (10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        if len(content) > MAX_FILE_SIZE:
            raise VFSError(f"File too large: {len(content)} bytes")

        real_path = self._get_real_path(vfs_path)
        tmp_path = None

        try:
            # Ensure parent directory exists
            real_path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: write to temp, then rename
            tmp_path = real_path.with_suffix(real_path.suffix + ".tmp")
            tmp_path.write_text(content, encoding=encoding)
            tmp_path.replace(real_path)
        except VFSError:
            raise
        except Exception as e:
            # Clean up temp file on failure
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()
            raise VFSError(f"Failed to write: {e}")

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
            vfs_dir: VFS directory path (e.g., "agrc://prompts", "prompts/subdir", "agrc://prompts/")

        Returns:
            List of entry names. Directories have "/" suffix appended.
            Empty list if: directory not found, empty directory, or OS error.
            Raises VFSError if: permission denied, path traversal detected.

        Raises:
            VFSError: If path traversal detected or read permission denied
        """
        # Handle empty or None input
        if not vfs_dir:
            return []

        # Normalize path: ensure scheme prefix
        if not vfs_dir.startswith(self.VFS_SCHEME):
            vfs_dir = self.VFS_SCHEME + vfs_dir

        # Extract VFS path without scheme, strip trailing slashes
        vfs_path = vfs_dir[len(self.VFS_SCHEME):].rstrip("/")

        # Handle VFS root: list top-level contents
        if not vfs_path:
            resolved = self._bundle_path
        else:
            # Check read permission
            if not self._has_permission(vfs_path, "r"):
                raise VFSError(f"Permission denied: read not allowed for {vfs_path}")

            real_dir = self._bundle_path / vfs_path

            # Security check: resolve symlinks and verify within bundle
            try:
                resolved = real_dir.resolve()
            except OSError:
                # Broken symlink or other OS error
                return []

            # Path traversal detection
            if not resolved.is_relative_to(self._bundle_path):
                raise VFSError(f"Path traversal detected: {vfs_path}")

        # Check if path is a valid directory
        if not resolved.exists() or not resolved.is_dir():
            return []

        # List contents
        result = []
        try:
            for entry in resolved.iterdir():
                name = entry.name
                if entry.is_dir():
                    name += "/"
                result.append(name)
        except PermissionError:
            return []
        except OSError:
            return []

        result.sort()
        return result

    def render_template(self, vfs_path: str, context: Dict[str, Any]) -> str:
        """
        Render template with context variables.

        Supports {{variable}} syntax. Uses unique placeholders to prevent
        injection attacks where context values contain {{other}} patterns.

        Args:
            vfs_path: VFS path to template
            context: Template variables

        Returns:
            Rendered template string
        """
        content = self.read(vfs_path)

        # Use unique placeholders to prevent double-replacement injection
        import uuid
        placeholders = {}
        for key, value in context.items():
            placeholder = f"__PH_{uuid.uuid4().hex}__"
            placeholders[placeholder] = str(value)
            content = content.replace(f"{{{{{key}}}}}", placeholder)

        # Replace placeholders with actual values
        for placeholder, value in placeholders.items():
            content = content.replace(placeholder, value)

        return content

    def create_dir(self, vfs_dir: str) -> None:
        """
        Create directory and parents if needed.

        Args:
            vfs_dir: VFS directory path to create

        Raises:
            VFSError: If permission denied or path invalid
        """
        if not vfs_dir.startswith(self.VFS_SCHEME):
            vfs_dir = self.VFS_SCHEME + vfs_dir

        vfs_path = vfs_dir[len(self.VFS_SCHEME):].strip("/")

        if not vfs_path:
            raise VFSError("Cannot create root directory")

        if not self._has_permission(vfs_path, "w"):
            raise VFSError("Permission denied")

        real_path = self._bundle_path / vfs_path
        real_path.mkdir(parents=True, exist_ok=True)

    def delete(self, vfs_path: str) -> None:
        """
        Delete file or empty directory.

        Args:
            vfs_path: VFS path to delete

        Raises:
            VFSError: If permission denied, path invalid, or directory not empty
        """
        if not self._has_permission(vfs_path, "w"):
            raise VFSError("Permission denied")

        real_path = self._get_real_path(vfs_path)

        if real_path.is_dir():
            if any(real_path.iterdir()):
                raise VFSError("Cannot delete non-empty directory")
            real_path.rmdir()
        else:
            real_path.unlink()

    def move(self, src: str, dst: str) -> None:
        """
        Move/rename file or directory.

        Args:
            src: Source VFS path
            dst: Destination VFS path

        Raises:
            VFSError: If permission denied or path invalid
        """
        # Check write permission on both source and destination
        if not self._has_permission(src, "w"):
            raise VFSError("Permission denied for source")
        if not self._has_permission(dst, "w"):
            raise VFSError("Permission denied for destination")

        src_path = self._get_real_path(src)

        # For destination, build path directly without full parsing
        if not dst.startswith(self.VFS_SCHEME):
            dst = self.VFS_SCHEME + dst
        dst_vfs_path = dst[len(self.VFS_SCHEME):].strip("/")
        dst_path = self._bundle_path / dst_vfs_path

        import shutil
        shutil.move(str(src_path), str(dst_path))

    def metadata(self, vfs_path: str) -> dict:
        """
        Get file/directory metadata.

        Args:
            vfs_path: VFS path

        Returns:
            Dict with size, mtime, is_dir, is_file

        Raises:
            VFSError: If path invalid
        """
        real_path = self._get_real_path(vfs_path)
        stat = real_path.stat()
        return {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "is_dir": real_path.is_dir(),
            "is_file": real_path.is_file(),
        }

    def is_valid(self) -> bool:
        """Check if bundle path is still valid (exists and is directory)."""
        return self._bundle_path.exists() and self._bundle_path.is_dir()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


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