"""
Template Resolver

Resolves {{key}} placeholders and {% %} control flow in strings with values from context.
Supports nested attribute access ({{user.name}}), recursive resolution,
VFS path resolution (agrc://...), and Jinja2-style control flow:

- {% if key %}...{% else %}...{% endif %}
- {% for var in list_key %}...{{ var }}...{% endfor %}
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any


class TemplateError(Exception):
    """Raised when template resolution fails."""
    pass


# ============================================================
# Control Flow Resolution ({% if %}, {% for %})
# ============================================================

def _get_context_value(key: str, context_getter: Callable[[str], Any]) -> Any:
    """Get value from context, handling dot access (shared helper)."""
    key = key.strip()
    if '.' in key:
        parts = key.split('.')
        obj = context_getter(parts[0])
        for part in parts[1:]:
            if obj is None:
                return None
            obj = obj.get(part) if isinstance(obj, dict) else getattr(obj, part, None)
        return obj
    return context_getter(key)


def resolve_control_flow(
    text: str,
    context_getter: Callable[[str], Any],
) -> str:
    """
    Resolve {% if %}...{% endif %} and {% for %}...{% endfor %} control blocks.

    This runs BEFORE {{key}} template resolution. Supports:
    - {% if key %}content{% else %}alt{% endif %}
    - {% if key %}content{% endif %}
    - {% for var in list_key %}...{{ var }}...{% endfor %}

    Args:
        text: String with control flow tags
        context_getter: Callable to get context values

    Returns:
        String with control flow blocks resolved to their rendered content.
    """
    if not isinstance(text, str) or ('{%' not in text):
        return text

    # Process for loops first (they may contain if blocks inside)
    text = _resolve_for_loops(text, context_getter)
    # Process if/else blocks
    text = _resolve_if_blocks(text, context_getter)

    return text


def _resolve_if_blocks(text: str, context_getter: Callable[[str], Any]) -> str:
    """Process {% if KEY %}...{% else %}...{% endif %} blocks iteratively."""
    pattern = re.compile(
        r'\{%\s*if\s+(.+?)\s*%\}(.*?)(?:\{%\s*else\s*%\}(.*?))?\{%\s*endif\s*%\}',
        re.DOTALL
    )

    while pattern.search(text):
        def _replace_if(m):
            condition_key = m.group(1).strip()
            true_content = m.group(2)
            false_content = m.group(3) or ''
            value = _get_context_value(condition_key, context_getter)
            return true_content if value else false_content

        text = pattern.sub(_replace_if, text, count=1)

    return text


def _resolve_for_loops(text: str, context_getter: Callable[[str], Any]) -> str:
    """Process {% for VAR in LIST_KEY %}...{% endfor %} blocks iteratively."""
    pattern = re.compile(
        r'\{%\s+for\s+(\w+)\s+in\s+(.+?)\s*%\}(.*?)\{%\s+endfor\s*%\}',
        re.DOTALL
    )

    while pattern.search(text):
        def _replace_for(m):
            var_name = m.group(1).strip()
            list_key = m.group(2).strip()
            content = m.group(3)

            items = _get_context_value(list_key, context_getter)
            if items is None:
                return ''
            if isinstance(items, (str, bytes, dict)):
                return ''
            try:
                items = list(items)
            except TypeError:
                return ''

            results = []
            for idx, item in enumerate(items):
                item_text = content
                # Replace {{ var }} and {{var}} with item value
                item_text = item_text.replace('{{ ' + var_name + ' }}', str(item))
                item_text = item_text.replace('{{' + var_name + '}}', str(item))
                # Loop variables
                item_text = item_text.replace('{{loop.iteration}}', str(idx + 1))
                item_text = item_text.replace('{{ loop.iteration }}', str(idx + 1))
                item_text = item_text.replace('{{loop.current_item}}', str(item))
                item_text = item_text.replace('{{ loop.current_item }}', str(item))
                results.append(item_text)

            return ''.join(results)

        text = pattern.sub(_replace_for, text, count=1)

    return text


def resolve_template(
    text: str | Any,
    context_getter: Callable[[str], Any],
    allow_missing: bool = False,
    max_depth: int = 10,
) -> str | Any:
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

    # Resolve control flow ({% if %}, {% for %}) before {{key}} placeholders
    text = resolve_control_flow(text, context_getter)

    # Pattern matches {{key}} where key is any characters except }
    pattern = re.compile(r'\{\{([^}]+)\}\}')

    def get_value(key: str) -> Any:
        """Get value from context, handling nested attribute access."""
        return _get_context_value(key, context_getter)

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
    data: dict[str, Any],
    context_getter: Callable[[str], Any],
    allow_missing: bool = False,
    max_depth: int = 10,
) -> dict[str, Any]:
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
    permissions: dict[str, bool] | None = None,
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
    except (VFSError, OSError):
        # If VFS resolution fails, return original value
        return value


def resolve_vfs_and_template(
    value: Any,
    context_getter: Callable[[str], Any],
    bundle_path_getter: Callable[[], Any],
    permissions: dict[str, bool] | None = None,
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
        # First resolve VFS path, then control flow, then templates
        value = resolve_vfs_path(value, bundle_path_getter, permissions)
        value = resolve_control_flow(value, context_getter)
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
