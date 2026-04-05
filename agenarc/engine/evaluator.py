"""
AST Safe Expression Evaluator

Safe evaluation of Python expressions using AST manipulation.
Used by Script_Node and condition evaluation.
"""

import ast
import operator as op
from typing import Any, Callable, Dict, Optional


class ASTEvaluatorError(Exception):
    """Raised when expression evaluation fails."""
    pass


class ASTEvaluator:
    """
    Safe AST-based expression evaluator.

    Evaluates Python expressions without using eval() or exec().
    Only allows safe operations defined in the whitelist.

    Usage:
        evaluator = ASTEvaluator()
        result = evaluator.evaluate("x + y", {"x": 1, "y": 2})  # Returns 3
    """

    # Safe binary operators
    BINARY_OPERATORS: Dict[ast.operator, Callable[[Any, Any], Any]] = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.FloorDiv: op.floordiv,
        ast.Mod: op.mod,
        ast.Pow: op.pow,
        ast.LShift: op.lshift,
        ast.RShift: op.rshift,
        ast.BitOr: op.or_,
        ast.BitXor: lambda a, b: a ^ b,  # XOR using ^ operator
        ast.BitAnd: op.and_,
        ast.MatMult: op.matmul,
    }

    # Safe unary operators
    UNARY_OPERATORS: Dict[ast.unaryop, Callable[[Any], Any]] = {
        ast.Invert: op.invert,
        ast.Not: op.not_,
        ast.UAdd: lambda x: +x,  # Unary positive
        ast.USub: lambda x: -x,  # Unary negative
    }

    # Safe comparison operators
    COMPARISON_OPERATORS: Dict[ast.cmpop, Callable[[Any, Any], bool]] = {
        ast.Eq: op.eq,
        ast.NotEq: op.ne,
        ast.Lt: op.lt,
        ast.LtE: op.le,
        ast.Gt: op.gt,
        ast.GtE: op.ge,
        ast.Is: op.is_,
        ast.IsNot: op.is_not,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
    }

    # Allowed built-in functions
    ALLOWED_BUILTINS: Dict[str, Callable[..., Any]] = {
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "sorted": sorted,
        "any": any,
        "all": all,
        "min": min,
        "max": max,
        "abs": abs,
        "sum": sum,
        "round": round,
        "isinstance": isinstance,
        "type": type,
        "getattr": getattr,
        "hasattr": hasattr,
    }

    def __init__(self, extra_builtins: Optional[Dict[str, Callable[..., Any]]] = None):
        """
        Initialize evaluator.

        Args:
            extra_builtins: Additional built-in functions to allow
        """
        self._builtins = self.ALLOWED_BUILTINS.copy()
        if extra_builtins:
            self._builtins.update(extra_builtins)

    def evaluate(
        self,
        expression: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Evaluate an expression safely.

        Args:
            expression: Python expression to evaluate
            context: Variables available in the expression

        Returns:
            Result of evaluation

        Raises:
            ASTEvaluatorError: If expression is invalid or unsafe
        """
        if context is None:
            context = {}

        try:
            # Parse the expression into an AST
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            raise ASTEvaluatorError(f"Invalid expression syntax: {e}")

        # Check for unsafe constructs
        self._check_tree(tree)

        # Evaluate the AST
        return self._eval_node(tree.body, context)

    def _check_tree(self, tree: ast.AST) -> None:
        """Check AST for unsafe constructs."""
        for node in ast.walk(tree):
            # Check for function calls that aren't allowed builtins
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name not in self._builtins:
                        raise ASTEvaluatorError(
                            f"Function '{func_name}' is not allowed. "
                            f"Allowed functions: {list(self.ALLOWED_BUILTINS.keys())}"
                        )
                elif isinstance(node.func, ast.Attribute):
                    # Attribute access like 'x.method' is not allowed
                    raise ASTEvaluatorError(
                        f"Attribute access is not allowed in expressions"
                    )
                else:
                    raise ASTEvaluatorError(
                        f"Unsupported function call type"
                    )

            # Check for subscript with non-simple index
            if isinstance(node, ast.Subscript):
                # Allow simple subscripts like x[0], x['key']
                pass  # Will be handled in evaluation

            # Check for Lambda (not allowed)
            if isinstance(node, ast.Lambda):
                raise ASTEvaluatorError("Lambda functions are not allowed")

            # Check for comprehension (not allowed)
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                raise ASTEvaluatorError("Comprehensions are not allowed")

            # Check for slice (not allowed)
            if isinstance(node, ast.Slice):
                raise ASTEvaluatorError("Slice operations are not allowed")

    def _eval_node(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        """Recursively evaluate an AST node."""
        # Literals
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Num):  # Python 3.7 compatibility
            return node.n
        if isinstance(node, ast.Str):  # Python 3.7 compatibility
            return node.s
        if isinstance(node, ast.Bytes):
            return node.s
        if isinstance(node, ast.List):
            return [self._eval_node(e, context) for e in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._eval_node(e, context) for e in node.elts)
        if isinstance(node, ast.Set):
            return {self._eval_node(e, context) for e in node.elts}
        if isinstance(node, ast.Dict):
            return {
                self._eval_node(k, context): self._eval_node(v, context)
                for k, v in zip(node.keys, node.values)
            }

        # Variables and attributes
        if isinstance(node, ast.Name):
            if node.id in context:
                return context[node.id]
            if node.id in self._builtins:
                return self._builtins[node.id]
            raise ASTEvaluatorError(f"Undefined variable: {node.id}")

        if isinstance(node, ast.Attribute):
            raise ASTEvaluatorError("Attribute access is not allowed")

        # Binary operations
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, context)
            right = self._eval_node(node.right, context)
            op_func = self.BINARY_OPERATORS.get(type(node.op))
            if op_func is None:
                raise ASTEvaluatorError(f"Unsupported binary operator: {node.op}")
            return op_func(left, right)

        # Unary operations
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, context)
            op_func = self.UNARY_OPERATORS.get(type(node.op))
            if op_func is None:
                raise ASTEvaluatorError(f"Unsupported unary operator: {node.op}")
            return op_func(operand)

        # Comparison operations
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, context)
            for op_node, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator, context)
                op_func = self.COMPARISON_OPERATORS.get(type(op_node))
                if op_func is None:
                    raise ASTEvaluatorError(f"Unsupported comparison: {op_node}")
                if not op_func(left, right):
                    return False
                left = right
            return True

        # Boolean operations
        if isinstance(node, ast.BoolOp):
            left = self._eval_node(node.values[0], context)
            is_and = isinstance(node.op, ast.And)
            for value in node.values[1:]:
                right = self._eval_node(value, context)
                if is_and:
                    left = left and right
                else:
                    left = left or right
            return left

        # If expressions (ternary)
        if isinstance(node, ast.IfExp):
            test = self._eval_node(node.test, context)
            if test:
                return self._eval_node(node.body, context)
            return self._eval_node(node.orelse, context)

        # Function calls (only allowed builtins)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                func_name = func.id
                if func_name not in self._builtins:
                    raise ASTEvaluatorError(f"Function '{func_name}' is not allowed")

                # Get function
                callable_func = self._builtins[func_name]

                # Evaluate arguments
                args = [self._eval_node(arg, context) for arg in node.args]

                # Evaluate keyword arguments (simplified - only support basic cases)
                kwargs = {}
                for kwarg in node.keywords:
                    if kwarg.arg:
                        kwargs[kwarg.arg] = self._eval_node(kwarg.value, context)

                return callable_func(*args, **kwargs)
            else:
                raise ASTEvaluatorError("Unsupported function call type")

        # Subscript operations
        if isinstance(node, ast.Subscript):
            value = self._eval_node(node.value, context)
            index = self._eval_node(node.slice, context)
            return value[index]

        # Index (Python 3.8 compatibility)
        if isinstance(node, ast.Index):
            return self._eval_node(node.value, context)

        raise ASTEvaluatorError(f"Unsupported AST node type: {type(node)}")


# Global evaluator instance
_default_evaluator: Optional[ASTEvaluator] = None


def get_evaluator() -> ASTEvaluator:
    """Get the default evaluator instance."""
    global _default_evaluator
    if _default_evaluator is None:
        _default_evaluator = ASTEvaluator()
    return _default_evaluator


def evaluate_expression(
    expression: str,
    context: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Convenience function to evaluate an expression.

    Args:
        expression: Python expression to evaluate
        context: Variables available in the expression

    Returns:
        Result of evaluation
    """
    return get_evaluator().evaluate(expression, context)
