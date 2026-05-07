"""
Template Resolver

Resolves {{key}} placeholders in strings with values from context.
Supports nested attribute access ({{user.name}}), recursive resolution,
and VFS path resolution (agrc://...).
"""

import re
from typing import Any, Callable, Dict, List, Optional, Union


class TemplateError(Exception):
    """Raised when template resolution fails."""
    pass


def resolve_template(
    text: Union[str, Any],
    context_getter: Callable[[str], Any],
    allow_missing: bool = False,
    max_depth: int = 10,
) -> Union[str, Any]:
    """
    Resolve {{key}} placeholders in text with values from context.

    Template format: {{key}} - resolved from context_getter(key)
    Nested access supported: {{user.name}} -> context_getter("user").name
    Recursive resolution: If resolved value contains more {{...}}, resolution continues.

    Args:
        text: String with {{key}} placeholders (or any non-string value)
        context_getter: Callable that takes a key and returns value from context
        allow_missing: If True, missing keys are replaced with empty string.
                       If False, raises TemplateError.
        max_depth: Maximum recursion depth for nested template resolution.

    Returns:
        String with resolved placeholders. Non-string inputs are returned as-is.

    Examples:
        resolve_template("Hello {{name}}!", lambda k: {"name": "World"}[k])
        # Returns: "Hello World!"

        resolve_template("Model: {{config.model}}", context.get)
        # Returns: "Model: gpt-4" (if config={"model": "gpt-4"})

        # Recursive resolution:
        # context = {"template": "{{name}}", "name": "Alice"}
        resolve_template("Hello {{template}}!", lambda k: context[k])
        # First pass: "{{name}}" -> "Alice"
        # Returns: "Hello Alice!"
    """
    if not isinstance(text, str):
        return text

    # Pattern matches {{key}} where key is any characters except }
    pattern = re.compile(r'\{\{([^}]+)\}\}')

    def get_value(key: str) -> Any:
        """Get value from context, handling nested attribute access."""
        key = key.strip()

        # Handle nested attribute access like user.name
        if '.' in key:
            parts = key.split('.')
            obj = context_getter(parts[0])
            for part in parts[1:]:
                if obj is None:
                    return None
                # Support both dict key access and object attribute access
                if isinstance(obj, dict):
                    obj = obj.get(part)
                else:
                    obj = getattr(obj, part, None)
            return obj

        return context_getter(key)

    def replacer(match):
        nonlocal max_depth

        if max_depth <= 0:
            return match.group(0)  # Return as-is to prevent infinite recursion

        key = match.group(1).strip()

        try:
            value = get_value(key)

            if value is None:
                if allow_missing:
                    return ""
                raise TemplateError(f"Template key not found: {key}")

            # Convert to string for potential template resolution
            resolved = str(value)

            # If resolved value contains templates, recursively resolve
            # Decrement depth to prevent infinite loops
            max_depth -= 1
            if '{{' in resolved and '}}' in resolved:
                resolved = resolve_template(resolved, context_getter, allow_missing, max_depth)

            return resolved

        except (KeyError, AttributeError):
            if allow_missing:
                return ""
            raise TemplateError(f"Template key not found: {key}")

    return pattern.sub(replacer, text)


def resolve_template_dict(
    data: Dict[str, Any],
    context_getter: Callable[[str], Any],
    allow_missing: bool = False,
    max_depth: int = 10,
) -> Dict[str, Any]:
    """
    Recursively resolve {{key}} placeholders in a dictionary.

    Only string values are resolved. Other types are preserved.

    Args:
        data: Dictionary with potential {{key}} placeholders
        context_getter: Callable that takes a key and returns value from context
        allow_missing: If True, missing keys are replaced with empty string.
        max_depth: Maximum recursion depth for nested template resolution.

    Returns:
        New dictionary with resolved placeholders.
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = resolve_template(value, context_getter, allow_missing, max_depth)
        elif isinstance(value, dict):
            result[key] = resolve_template_dict(value, context_getter, allow_missing, max_depth)
        elif isinstance(value, list):
            result[key] = [
                resolve_template(item, context_getter, allow_missing, max_depth)
                if isinstance(item, str) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def resolve_template_any(
    value: Any,
    context_getter: Callable[[str], Any],
    allow_missing: bool = False,
    max_depth: int = 10,
) -> Any:
    """
    Resolve {{key}} placeholders in any value type.

    Args:
        value: Any value (string, dict, list, etc.)
        context_getter: Callable that takes a key and returns value from context
        allow_missing: If True, missing keys are replaced with empty string.
        max_depth: Maximum recursion depth for nested template resolution.

    Returns:
        Value with resolved placeholders.
    """
    if isinstance(value, str):
        return resolve_template(value, context_getter, allow_missing, max_depth)
    elif isinstance(value, dict):
        return resolve_template_dict(value, context_getter, allow_missing, max_depth)
    elif isinstance(value, list):
        return [
            resolve_template_any(item, context_getter, allow_missing, max_depth)
            for item in value
        ]
    else:
        return value


def resolve_vfs_path(
    value: str,
    bundle_path_getter: Callable[[], "Path"],
    permissions: Optional[Dict[str, bool]] = None,
) -> str:
    """
    Resolve VFS path (agrc://...) to actual file content.

    Args:
        value: String value that might be a VFS path
        bundle_path_getter: Callable returning the bundle Path
        permissions: Optional permissions dict for VFS access

    Returns:
        File content if value is a VFS path, otherwise original value
    """
    if not isinstance(value, str):
        return value

    if not value.startswith("agrc://"):
        return value

    try:
        from pathlib import Path
        from agenarc.vfs.filesystem import VFS, VFSError

        bundle_path = bundle_path_getter()
        if not bundle_path:
            return value

        vfs = VFS(Path(bundle_path), permissions)
        return vfs.read(value)
    except Exception:
        # If VFS resolution fails, return original value
        return value


def resolve_vfs_and_template(
    value: Any,
    context_getter: Callable[[str], Any],
    bundle_path_getter: Callable[[], Any],
    permissions: Optional[Dict[str, bool]] = None,
    allow_missing: bool = False,
    max_depth: int = 10,
) -> Any:
    """
    Resolve VFS paths and {{key}} templates in any value.

    Flow: VFS path -> file content -> template resolution

    Args:
        value: Any value (string, dict, list, etc.)
        context_getter: Callable that takes a key and returns value from context
        bundle_path_getter: Callable that returns the bundle Path
        permissions: Optional permissions dict for VFS access
        allow_missing: If True, missing template keys are replaced with empty string.
        max_depth: Maximum recursion depth for nested template resolution.

    Returns:
        Value with VFS paths resolved to content and templates resolved.
    """
    if isinstance(value, str):
        # First resolve VFS path, then templates
        value = resolve_vfs_path(value, bundle_path_getter, permissions)
        return resolve_template(value, context_getter, allow_missing, max_depth)
    elif isinstance(value, dict):
        # Recursively resolve dict values
        return {
            k: resolve_vfs_and_template(v, context_getter, bundle_path_getter, permissions, allow_missing, max_depth)
            for k, v in value.items()
        }
    elif isinstance(value, list):
        # Recursively resolve list items
        return [
            resolve_vfs_and_template(item, context_getter, bundle_path_getter, permissions, allow_missing, max_depth)
            for item in value
        ]
    else:
        return value
