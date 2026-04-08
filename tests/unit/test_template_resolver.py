"""Unit tests for template resolution in evaluator.py."""

import pytest
from agenarc.engine.evaluator import (
    resolve_template,
    resolve_template_dict,
    resolve_template_any,
    resolve_vfs_path,
    resolve_vfs_and_template,
    TemplateError,
)


class TestResolveTemplate:
    """Tests for resolve_template function."""

    def test_resolve_simple_template(self):
        """Test resolving a simple {{key}} template."""
        context = {"name": "World", "greeting": "Hello"}
        result = resolve_template("Hello {{name}}!", lambda k: context.get(k))
        assert result == "Hello World!"

    def test_resolve_multiple_templates(self):
        """Test resolving multiple templates."""
        context = {"user": "Alice", "assistant": "Bob"}
        result = resolve_template("{{user}} and {{assistant}}", lambda k: context.get(k))
        assert result == "Alice and Bob"

    def test_resolve_template_with_missing_key_allow(self):
        """Test resolving template with missing key (allow_missing=True)."""
        context = {"name": "World"}
        result = resolve_template("Hello {{missing}}!", lambda k: context.get(k), allow_missing=True)
        assert result == "Hello !"

    def test_resolve_template_with_missing_key_disallow(self):
        """Test resolving template with missing key (allow_missing=False)."""
        context = {"name": "World"}
        with pytest.raises(TemplateError, match="Template key not found"):
            resolve_template("Hello {{missing}}!", lambda k: context.get(k), allow_missing=False)

    def test_resolve_template_no_template(self):
        """Test resolving string without templates."""
        context = {"name": "World"}
        result = resolve_template("Hello World!", lambda k: context.get(k))
        assert result == "Hello World!"

    def test_resolve_template_non_string(self):
        """Test that non-string values are returned as-is."""
        context = {"name": "World"}
        assert resolve_template(123, lambda k: context.get(k)) == 123
        assert resolve_template(None, lambda k: context.get(k)) is None
        assert resolve_template({"a": 1}, lambda k: context.get(k)) == {"a": 1}

    def test_resolve_template_with_whitespace(self):
        """Test resolving template with whitespace around key."""
        context = {"name": "World"}
        result = resolve_template("Hello {{ name }}!", lambda k: context.get(k.strip()))
        assert result == "Hello World!"


class TestResolveTemplateDict:
    """Tests for resolve_template_dict function."""

    def test_resolve_dict_values(self):
        """Test resolving templates in dict values."""
        context = {"user": "Alice", "model": "gpt-4"}
        data = {
            "prompt": "Hello {{user}}!",
            "model": "{{model}}",
        }
        result = resolve_template_dict(data, lambda k: context.get(k))
        assert result["prompt"] == "Hello Alice!"
        assert result["model"] == "gpt-4"

    def test_resolve_nested_dict(self):
        """Test resolving templates in nested dicts."""
        context = {"user": "Alice"}
        data = {
            "config": {
                "prompt": "Hello {{user}}!",
            }
        }
        result = resolve_template_dict(data, lambda k: context.get(k))
        assert result["config"]["prompt"] == "Hello Alice!"

    def test_resolve_dict_preserves_non_string(self):
        """Test that non-string dict values are preserved."""
        context = {"name": "Alice"}
        data = {
            "count": 42,
            "enabled": True,
            "items": [1, 2, 3],
        }
        result = resolve_template_dict(data, lambda k: context.get(k))
        assert result["count"] == 42
        assert result["enabled"] is True
        assert result["items"] == [1, 2, 3]

    def test_resolve_dict_with_list(self):
        """Test resolving templates in list values."""
        context = {"name": "Alice"}
        data = {
            "items": ["Hello {{name}}!", "Bye {{name}}!"],
        }
        result = resolve_template_dict(data, lambda k: context.get(k))
        assert result["items"] == ["Hello Alice!", "Bye Alice!"]


class TestResolveTemplateAny:
    """Tests for resolve_template_any function."""

    def test_resolve_any_string(self):
        """Test resolving any with string."""
        context = {"name": "Alice"}
        result = resolve_template_any("Hello {{name}}!", lambda k: context.get(k))
        assert result == "Hello Alice!"

    def test_resolve_any_dict(self):
        """Test resolving any with dict."""
        context = {"name": "Alice"}
        result = resolve_template_any({"prompt": "Hello {{name}}!"}, lambda k: context.get(k))
        assert result == {"prompt": "Hello Alice!"}

    def test_resolve_any_list(self):
        """Test resolving any with list."""
        context = {"name": "Alice"}
        result = resolve_template_any(["Hello {{name}}!", "Bye {{name}}!"], lambda k: context.get(k))
        assert result == ["Hello Alice!", "Bye Alice!"]

    def test_resolve_any_primitive(self):
        """Test resolving any with primitive types."""
        context = {"name": "Alice"}
        assert resolve_template_any(42, lambda k: context.get(k)) == 42
        assert resolve_template_any(True, lambda k: context.get(k)) is True
        assert resolve_template_any(None, lambda k: context.get(k)) is None


class TestResolveVfsPath:
    """Tests for resolve_vfs_path function."""

    def test_resolve_vfs_path_non_vfs(self):
        """Test that non-VFS strings are returned as-is."""
        def bundle_getter():
            return None

        result = resolve_vfs_path("Hello World!", bundle_getter)
        assert result == "Hello World!"

    def test_resolve_vfs_path_no_bundle(self):
        """Test that missing bundle returns original value."""
        def bundle_getter():
            return None

        result = resolve_vfs_path("agrc://prompts/test.pt", bundle_getter)
        assert result == "agrc://prompts/test.pt"

    def test_resolve_vfs_path_with_bundle(self, tmp_path):
        """Test resolving VFS path to file content."""
        # Create a mock bundle with a prompt file
        bundle = tmp_path / "test_agent.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()
        prompt_file = prompts_dir / "system.pt"
        prompt_file.write_text("You are {{user_name}}'s assistant.", encoding="utf-8")

        def bundle_getter():
            return str(bundle)

        result = resolve_vfs_path("agrc://prompts/system.pt", bundle_getter)
        assert result == "You are {{user_name}}'s assistant."

    def test_resolve_vfs_path_non_string(self):
        """Test that non-string values are returned as-is."""
        def bundle_getter():
            return "/path/to/bundle"

        assert resolve_vfs_path(123, bundle_getter) == 123
        assert resolve_vfs_path(None, bundle_getter) is None


class TestResolveVfsAndTemplate:
    """Tests for resolve_vfs_and_template function."""

    def test_resolve_vfs_then_template(self, tmp_path):
        """Test resolving VFS path first, then templates."""
        # Create a mock bundle with a prompt file containing template
        bundle = tmp_path / "test_agent.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()
        prompt_file = prompts_dir / "system.pt"
        prompt_file.write_text("You are {{user_name}}'s assistant.", encoding="utf-8")

        def context_getter(key):
            lookup = {"user_name": "Alice"}
            return lookup.get(key)

        def bundle_getter():
            return str(bundle)

        result = resolve_vfs_and_template(
            "agrc://prompts/system.pt",
            context_getter,
            bundle_getter,
            allow_missing=True
        )
        assert result == "You are Alice's assistant."

    def test_resolve_template_only(self):
        """Test resolving template without VFS path."""
        def context_getter(key):
            lookup = {"user_name": "Alice"}
            return lookup.get(key)

        def bundle_getter():
            return None

        result = resolve_vfs_and_template(
            "Hello {{user_name}}!",
            context_getter,
            bundle_getter,
            allow_missing=True
        )
        assert result == "Hello Alice!"

    def test_resolve_vfs_and_template_dict(self, tmp_path):
        """Test resolving VFS and templates in dict."""
        bundle = tmp_path / "test_agent.agrc"
        bundle.mkdir()
        prompts_dir = bundle / "prompts"
        prompts_dir.mkdir()
        prompt_file = prompts_dir / "system.pt"
        prompt_file.write_text("You are {{user_name}}'s assistant.", encoding="utf-8")

        def context_getter(key):
            lookup = {"user_name": "Alice", "model": "gpt-4"}
            return lookup.get(key)

        def bundle_getter():
            return str(bundle)

        data = {
            "system_prompt": "agrc://prompts/system.pt",
            "model": "{{model}}",
        }

        result = resolve_vfs_and_template(data, context_getter, bundle_getter, allow_missing=True)
        assert result["system_prompt"] == "You are Alice's assistant."
        assert result["model"] == "gpt-4"


class TestRecursiveTemplateResolution:
    """Tests for recursive template resolution."""

    def test_recursive_single_level(self):
        """Test recursive resolution with single level indirection."""
        # context = {"template": "{{name}}", "name": "Alice"}
        context = {"name": "Alice", "template": "Hello {{name}}!"}
        result = resolve_template("{{template}}", lambda k: context.get(k))
        assert result == "Hello Alice!"

    def test_recursive_double_level(self):
        """Test recursive resolution with double level indirection."""
        # context = {"a": "{{b}}", "b": "{{c}}", "c": "Alice"}
        context = {"c": "Alice", "b": "{{c}}", "a": "{{b}}"}
        result = resolve_template("{{a}}", lambda k: context.get(k))
        assert result == "Alice"

    def test_recursive_with_text_around(self):
        """Test recursive resolution with text around templates."""
        context = {"greeting": "Hello", "name": "Alice", "combined": "{{greeting}} {{name}}!"}
        result = resolve_template("Message: {{combined}}", lambda k: context.get(k))
        assert result == "Message: Hello Alice!"

    def test_recursive_max_depth_limit(self):
        """Test that max_depth prevents infinite recursion."""
        # Create a circular reference scenario
        context = {"a": "{{b}}", "b": "{{a}}"}
        # Should not infinite loop, just returns after max_depth iterations
        result = resolve_template("{{a}}", lambda k: context.get(k), allow_missing=True, max_depth=3)
        # After 3 depth levels, it should stop resolving (result may still have {{...}})
        # The key is it should NOT raise an error and should return something
        assert isinstance(result, str)

    def test_recursive_preserves_original_context_values(self):
        """Test that original context values are not modified."""
        context = {"template": "{{name}}", "name": "Alice"}
        result = resolve_template("{{template}}", lambda k: context.get(k))
        assert result == "Alice"
        # Original context should be unchanged
        assert context["template"] == "{{name}}"
        assert context["name"] == "Alice"

    def test_recursive_with_dot_access(self):
        """Test recursive resolution with dot notation."""
        # Note: dot access like {{user.name}} means:
        # - lookup key "user" in context -> get {"name": "Alice"}
        # - then getattr(..., "name") -> "Alice"
        context = {"user": {"name": "Alice"}, "template": "Hi {{user.name}}"}
        result = resolve_template("{{template}}", lambda k: context.get(k))
        assert result == "Hi Alice"

    def test_recursive_chain_with_dot_access(self):
        """Test recursive resolution where resolved value contains dot-access template."""
        context = {"user_name": "Alice", "user_key": "user", "template": "Hi {{user_name}}!"}
        # template -> "Hi {{user_name}}!" -> "Hi Alice!"
        result = resolve_template("{{template}}", lambda k: context.get(k))
        assert result == "Hi Alice!"
