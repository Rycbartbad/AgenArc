"""Unit tests for engine/evaluator.py."""

import pytest
from agenarc.engine.evaluator import ASTEvaluator, ASTEvaluatorError, evaluate_expression


class TestASTEvaluator:
    """Tests for ASTEvaluator."""

    def test_evaluator_creation(self):
        """Test evaluator can be created."""
        evaluator = ASTEvaluator()
        assert evaluator is not None

    def test_evaluate_number(self):
        """Test evaluating a number."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("42")
        assert result == 42

    def test_evaluate_string(self):
        """Test evaluating a string."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate('"hello"')
        assert result == "hello"

    def test_evaluate_boolean_true(self):
        """Test evaluating True."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("True")
        assert result is True

    def test_evaluate_boolean_false(self):
        """Test evaluating False."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("False")
        assert result is False

    def test_evaluate_list(self):
        """Test evaluating a list."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_evaluate_dict(self):
        """Test evaluating a dict."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate('{"a": 1, "b": 2}')
        assert result == {"a": 1, "b": 2}

    def test_evaluate_tuple(self):
        """Test evaluating a tuple."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("(1, 2, 3)")
        assert result == (1, 2, 3)


class TestASTEvaluatorArithmetic:
    """Tests for arithmetic operations."""

    def test_addition(self):
        """Test addition."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("1 + 2")
        assert result == 3

    def test_subtraction(self):
        """Test subtraction."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("5 - 3")
        assert result == 2

    def test_multiplication(self):
        """Test multiplication."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("3 * 4")
        assert result == 12

    def test_division(self):
        """Test division."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("10 / 2")
        assert result == 5.0

    def test_floor_division(self):
        """Test floor division."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("10 // 3")
        assert result == 3

    def test_modulo(self):
        """Test modulo."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("10 % 3")
        assert result == 1

    def test_power(self):
        """Test power operation."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("2 ** 3")
        assert result == 8

    def test_unary_negative(self):
        """Test unary negative."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("-5")
        assert result == -5

    def test_unary_positive(self):
        """Test unary positive."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("+5")
        assert result == 5


class TestASTEvaluatorComparisons:
    """Tests for comparison operations."""

    def test_equality(self):
        """Test equality comparison."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("1 == 1")
        assert result is True

    def test_inequality(self):
        """Test inequality comparison."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("1 != 2")
        assert result is True

    def test_less_than(self):
        """Test less than."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("1 < 2")
        assert result is True

    def test_less_than_or_equal(self):
        """Test less than or equal."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("2 <= 2")
        assert result is True

    def test_greater_than(self):
        """Test greater than."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("2 > 1")
        assert result is True

    def test_greater_than_or_equal(self):
        """Test greater than or equal."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("2 >= 2")
        assert result is True


class TestASTEvaluatorLogical:
    """Tests for logical operations."""

    def test_and_true(self):
        """Test logical and with True values."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("True and True")
        assert result is True

    def test_and_false(self):
        """Test logical and with False value."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("True and False")
        assert result is False

    def test_or_true(self):
        """Test logical or with True value."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("False or True")
        assert result is True

    def test_or_false(self):
        """Test logical or with False values."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("False or False")
        assert result is False

    def test_not(self):
        """Test logical not."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("not True")
        assert result is False


class TestASTEvaluatorContext:
    """Tests for context variable access."""

    def test_context_variable(self):
        """Test accessing variables from context."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("x + y", {"x": 10, "y": 20})
        assert result == 30

    def test_context_string(self):
        """Test context with string variables."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate('name + " world"', {"name": "hello"})
        assert result == "hello world"

    def test_missing_variable(self):
        """Test missing variable raises error."""
        evaluator = ASTEvaluator()
        with pytest.raises(ASTEvaluatorError, match="Undefined variable"):
            evaluator.evaluate("x + 1", {})

    def test_builtin_function_len(self):
        """Test len builtin function."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("len([1, 2, 3])")
        assert result == 3

    def test_builtin_function_str(self):
        """Test str builtin function."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("str(42)")
        assert result == "42"

    def test_builtin_function_int(self):
        """Test int builtin function."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("int(42.9)")
        assert result == 42

    def test_builtin_function_bool(self):
        """Test bool builtin function."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("bool(0)")
        assert result is False
        result = evaluator.evaluate("bool(1)")
        assert result is True

    def test_builtin_function_isinstance(self):
        """Test isinstance builtin function."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("isinstance(42, int)")
        assert result is True


class TestASTEvaluatorTernary:
    """Tests for ternary expressions."""

    def test_ternary_true(self):
        """Test ternary when condition is true."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("1 if True else 0")
        assert result == 1

    def test_ternary_false(self):
        """Test ternary when condition is false."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("1 if False else 0")
        assert result == 0


class TestASTEvaluatorMembership:
    """Tests for membership operations."""

    def test_in_list(self):
        """Test in operator with list."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("2 in [1, 2, 3]")
        assert result is True

    def test_not_in_list(self):
        """Test not in operator with list."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("4 not in [1, 2, 3]")
        assert result is True

    def test_in_string(self):
        """Test in operator with string."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate('"ello" in "hello"')
        assert result is True


class TestASTEvaluatorEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_expression(self):
        """Test empty expression."""
        evaluator = ASTEvaluator()
        with pytest.raises(ASTEvaluatorError):
            evaluator.evaluate("")

    def test_invalid_syntax(self):
        """Test invalid syntax raises error."""
        evaluator = ASTEvaluator()
        with pytest.raises(ASTEvaluatorError, match="Invalid expression syntax"):
            evaluator.evaluate("x + ")

    def test_nested_expressions(self):
        """Test nested expressions."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("(1 + 2) * (3 + 4)")
        assert result == 21

    def test_complex_expression(self):
        """Test complex expression."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("2 ** 3 + 4 * 5")
        assert result == 28  # 8 + 20 = 28

    def test_function_with_context(self):
        """Test calling function with context variable."""
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("len(items)", {"items": [1, 2, 3]})
        assert result == 3


class TestEvaluateExpression:
    """Tests for the convenience function."""

    def test_evaluate_expression_function(self):
        """Test the convenience evaluate_expression function."""
        result = evaluate_expression("1 + 2")
        assert result == 3

    def test_evaluate_expression_with_context(self):
        """Test evaluate_expression with context."""
        result = evaluate_expression("x * 2", {"x": 5})
        assert result == 10
