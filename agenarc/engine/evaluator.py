"""
AST Safe Expression Evaluator

Trust-based autonomous expression evaluator for Script_Node.
基于"信任 AI"原则：允许标准操作，仅拦截足以崩溃解释器的内核属性。

Features:
- 黑名单混合模式：仅拦截 __globals__, __builtins__, func_code 等危险属性
- 允许所有标准方法调用 (split, append, json, regex 等)
- 支持推导式 (ListComp, DictComp, SetComp)
- SafeContext 包装器：防止内存溢出
- Gas 计费机制：防止无限循环
"""

import ast
import operator as op
import sys
import tracemalloc
from typing import Any, Callable, Dict, List, Optional, Set


class ASTEvaluatorError(Exception):
    """Raised when expression evaluation fails."""
    pass


class GasExceededError(ASTEvaluatorError):
    """Raised when gas budget is exhausted."""
    pass


class MemoryLimitError(ASTEvaluatorError):
    """Raised when SafeContext memory limit is exceeded."""
    pass


# Dangerous attributes that can crash or compromise the interpreter
DANGEROUS_ATTRIBUTES: Set[str] = {
    # Interpreter internals
    "__globals__",
    "__builtins__",
    "__class__",
    "__bases__",
    "__mro__",
    "__subclasses__",
    "__code__",
    "__func__",
    "__self__",
    "__closure__",
    "__dicto__",
    "__module__",
    "__loader__",
    "__spec__",
    "__doc__",
    # Frame and traceback
    "f_back",
    "f_builtins",
    "f_code",
    "f_globals",
    "f_locals",
    "f_lasti",
    "f_lineno",
    "tb_frame",
    "tb_lasti",
    "tb_lineno",
    "tb_next",
    # Type internals
    "__init__",
    "__new__",
    "__metaclass__",
    "__prepare__",
    "__slots__",
    "__weakref__",
    # System escape
    "system",
    "popen",
    "spawn",
    "fork",
    "exec",
    "eval",
    "exec_file",
    "run_code",
    # File operations via os
    "remove",
    "unlink",
    "rmdir",
    "rename",
    "chmod",
    "chown",
    # Import machinery
    "__import__",
    "import_module",
}


class SafeContext:
    """
    Memory-bounded context wrapper.

    Wraps evaluation context to prevent unbounded memory allocation.
    Uses tracemalloc to track memory usage and enforce limits.
    """

    def __init__(self, data: Dict[str, Any], max_memory_mb: int = 128):
        self._data = data
        self._max_memory_bytes = max_memory_mb * 1024 * 1024
        self._current_memory = 0
        self._tracked_ids: Set[int] = set()

    def get(self, key: str, default: Any = None) -> Any:
        value = self._data.get(key, default)
        if value is not None:
            self._track_value(value)
        return value

    def _track_value(self, value: Any) -> None:
        """Track memory usage of a value."""
        value_id = id(value)
        if value_id not in self._tracked_ids:
            size = sys.getsizeof(value)
            # Only track if it's a container (more likely to be large)
            if isinstance(value, (list, dict, set, str, bytes)):
                try:
                    tracemalloc.start()
                    snapshot = tracemalloc.take_snapshot()
                    stats = snapshot.statistics('lineno')
                    total = sum(stat.size for stat in stats)
                    tracemalloc.stop()
                    self._current_memory += total
                except Exception:
                    # Fallback to sys.getsizeof
                    self._current_memory += size

                if self._current_memory > self._max_memory_bytes:
                    raise MemoryLimitError(
                        f"Expression evaluation exceeded memory limit "
                        f"({self._max_memory_bytes / 1024 / 1024:.1f} MB)"
                    )
            self._tracked_ids.add(value_id)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def keys(self):
        return self._data.keys()


class ASTEvaluator:
    """
    Trust-based AST expression evaluator.

    Philosophy: Allow everything except explicitly dangerous operations.
    This enables Agent's meta-programming capabilities while maintaining
    basic safety invariants.

    Usage:
        evaluator = ASTEvaluator(autonomy_level=2)
        result = evaluator.evaluate("x.split('.')", {"x": "a.b.c"})

        # With gas control
        evaluator = ASTEvaluator(gas_budget=500)
        result = evaluator.evaluate("sum(range(1000))", {})  # May raise GasExceededError
    """

    # Safe binary operators
    BINARY_OPERATORS: Dict[type[ast.operator], Callable[[Any, Any], Any]] = {
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
        ast.BitXor: lambda a, b: a ^ b,
        ast.BitAnd: op.and_,
        ast.MatMult: op.matmul,
    }

    # Safe unary operators
    UNARY_OPERATORS: Dict[type[ast.unaryop], Callable[[Any], Any]] = {
        ast.Invert: op.invert,
        ast.Not: op.not_,
        ast.UAdd: lambda x: +x,
        ast.USub: lambda x: -x,
    }

    # Safe comparison operators
    COMPARISON_OPERATORS: Dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
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

    # Allowed built-in functions (whitelist - available at all trust levels)
    ALLOWED_BUILTINS: Dict[str, Callable[..., Any]] = {
        # Type conversion
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "frozenset": frozenset,
        "bytes": bytes,
        "bytearray": bytearray,
        # Sequence operations
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "sorted": sorted,
        "reversed": reversed,
        "any": any,
        "all": all,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "pow": pow,
        "divmod": divmod,
        # Type checking
        "isinstance": isinstance,
        "issubclass": issubclass,
        "type": type,
        "callable": callable,
        # Object inspection
        "getattr": getattr,
        "setattr": setattr,
        "hasattr": hasattr,
        "delattr": delattr,
        "vars": vars,
        "dir": dir,
        "id": id,
        "hash": hash,
        "repr": repr,
        "ascii": ascii,
        "format": format,
        "ord": ord,
        "chr": chr,
        "bin": bin,
        "oct": oct,
        "hex": hex,
        # String operations
        "slice": slice,
        # Container builders
        "complex": complex,
    }

    # Extended builtins for level_2+
    LEVEL2_BUILTINS: Dict[str, Callable[..., Any]] = {
        "open": open,
        "compile": compile,
        "eval": eval,
        "exec": exec,
        "__import__": __import__,
    }

    def __init__(
        self,
        autonomy_level: int = 1,
        gas_budget: int = 1000,
        max_memory_mb: int = 128,
        extra_builtins: Optional[Dict[str, Callable[..., Any]]] = None,
    ):
        """
        Initialize evaluator with trust-based autonomy.

        Args:
            autonomy_level: Trust level (1=Supervised, 2=Autonomous, 3=Self-Evolving)
            gas_budget: Operations allowed before GasExceededError
            max_memory_mb: Memory limit for SafeContext
            extra_builtins: Additional functions to allow
        """
        self._autonomy_level = autonomy_level
        self._gas_budget = gas_budget
        self._gas_used = 0
        self._max_memory_mb = max_memory_mb
        self._enabled_features: Set[str] = {"comprehensions", "attribute_access"}

        self._builtins = self.ALLOWED_BUILTINS.copy()
        if autonomy_level >= 2:
            self._builtins.update(self.LEVEL2_BUILTINS)
        if extra_builtins:
            self._builtins.update(extra_builtins)

    def enable_feature(self, feature: str) -> None:
        """Enable an optional feature."""
        self._enabled_features.add(feature)

    def disable_feature(self, feature: str) -> None:
        """Disable an optional feature."""
        self._enabled_features.discard(feature)

    def _consume_gas(self, amount: int = 1) -> None:
        """Consume gas budget."""
        self._gas_used += amount
        if self._gas_used > self._gas_budget:
            raise GasExceededError(
                f"Expression evaluation exceeded gas budget ({self._gas_budget}). "
                f"Possible infinite loop."
            )

    def evaluate(
        self,
        expression: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Evaluate an expression with trust-based autonomy.

        Args:
            expression: Python expression to evaluate
            context: Variables available in the expression

        Returns:
            Result of evaluation

        Raises:
            ASTEvaluatorError: If expression is invalid or unsafe
            GasExceededError: If gas budget is exceeded
            MemoryLimitError: If memory limit is exceeded
        """
        self._gas_used = 0
        if context is None:
            context = {}

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            raise ASTEvaluatorError(f"Invalid expression syntax: {e}")

        safe_context = SafeContext(context, self._max_memory_mb)
        return self._eval_node(tree.body, safe_context)

    def _check_tree(self, tree: ast.AST) -> None:
        """Check AST for dangerous constructs."""
        for node in ast.walk(tree):
            self._consume_gas(1)

            # Check for function calls
            if isinstance(node, ast.Call):
                self._check_call(node)

            # Check for attribute access
            if isinstance(node, ast.Attribute):
                self._check_attribute(node)

            # Check for comprehensions
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                if "comprehensions" not in self._enabled_features:
                    raise ASTEvaluatorError(
                        "Comprehensions are not enabled. "
                        "Use enable_feature('comprehensions') or autonomy_level >= 2."
                    )

            # Check for Lambda
            if isinstance(node, ast.Lambda):
                raise ASTEvaluatorError("Lambda functions are not allowed")

            # Check for Slice (allowed in subscript context)
            if isinstance(node, ast.Slice) and not isinstance(node.parent, ast.Subscript):
                raise ASTEvaluatorError("Standalone slice operations are not allowed")

    def _check_call(self, node: ast.Call) -> None:
        """Check if a function call is allowed."""
        func = node.func

        if isinstance(func, ast.Name):
            func_name = func.id
            if func_name not in self._builtins:
                raise ASTEvaluatorError(
                    f"Function '{func_name}' is not allowed. "
                    f"Allowed: {list(self._builtins.keys())}"
                )

        elif isinstance(func, ast.Attribute):
            # Allow attribute access for method calls like x.split()
            attr_name = func.attr
            if attr_name in DANGEROUS_ATTRIBUTES:
                raise ASTEvaluatorError(
                    f"Attribute access to '{attr_name}' is not allowed. "
                    f"This attribute can compromise interpreter safety."
                )
            # Continue - will be checked at evaluation time

        elif isinstance(func, ast.Call):
            # Nested call
            self._check_call(func)

    def _check_attribute(self, node: ast.Attribute) -> None:
        """Check if attribute access is allowed."""
        attr_name = node.attr
        if attr_name in DANGEROUS_ATTRIBUTES:
            raise ASTEvaluatorError(
                f"Attribute '{attr_name}' is not allowed. "
                f"It can compromise interpreter safety."
            )

    def _eval_node(self, node: ast.AST, context: SafeContext) -> Any:
        """Recursively evaluate an AST node."""
        self._consume_gas(1)

        # Literals
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.Str):
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

        # Variables
        if isinstance(node, ast.Name):
            if node.id in context:
                return context.get(node.id)
            if node.id in self._builtins:
                return self._builtins[node.id]
            raise ASTEvaluatorError(f"Undefined variable: {node.id}")

        # Attribute access (TRUST-BASED: allow most attributes)
        if isinstance(node, ast.Attribute):
            value = self._eval_node(node.value, context)
            attr_name = node.attr

            # Final safety check at evaluation time
            if attr_name in DANGEROUS_ATTRIBUTES:
                raise ASTEvaluatorError(
                    f"Attribute '{attr_name}' is not allowed"
                )

            return getattr(value, attr_name)

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

        # List comprehensions
        if isinstance(node, ast.ListComp):
            return self._eval_comprehension(
                node.elt,
                node.generators,
                context
            )

        # Set comprehensions
        if isinstance(node, ast.SetComp):
            return self._eval_comprehension(
                node.elt,
                node.generators,
                context,
                result_type=set
            )

        # Dict comprehensions
        if isinstance(node, ast.DictComp):
            return self._eval_dict_comprehension(
                node.key,
                node.value,
                node.generators,
                context
            )

        # Generator expressions
        if isinstance(node, ast.GeneratorExp):
            return self._eval_comprehension(
                node.elt,
                node.generators,
                context
            )

        # Function calls
        if isinstance(node, ast.Call):
            return self._eval_call(node, context)

        # Subscript operations
        if isinstance(node, ast.Subscript):
            value = self._eval_node(node.value, context)
            index = self._eval_node(node.slice, context)
            return value[index]

        # Index (Python 3.8 compatibility)
        if isinstance(node, ast.Index):
            return self._eval_node(node.value, context)

        raise ASTEvaluatorError(f"Unsupported AST node type: {type(node)}")

    def _eval_comprehension(
        self,
        elt: ast.AST,
        generators: List[ast.comprehension],
        context: SafeContext,
        result_type: type = list,
    ) -> Any:
        """Evaluate list/set comprehension."""
        result = result_type() if result_type in (set,) else []

        def process_generator(gen_idx: int, current_values: List[Any]) -> None:
            generator = generators[gen_idx]

            # Evaluate iterable
            iterable = self._eval_node(generator.iter, context)

            for item in iterable:
                # Check if condition
                if generator.ifs:
                    if not all(self._eval_node(if_.test, context) for if_ in generator.ifs):
                        continue

                # Bind the variable
                target = generator.target
                if isinstance(target, ast.Name):
                    context._data[target.id] = item

                if gen_idx == len(generators) - 1:
                    # Last generator - produce element
                    value = self._eval_node(elt, context)
                    if result_type == set:
                        result.add(value)
                    else:
                        result.append(value)

                    self._consume_gas(1)
                    if self._gas_used > self._gas_budget:
                        raise GasExceededError(f"Comprehension exceeded gas budget")
                else:
                    process_generator(gen_idx + 1, current_values + [item])

        process_generator(0, [])
        return result

    def _eval_dict_comprehension(
        self,
        key_elt: ast.AST,
        value_elt: ast.AST,
        generators: List[ast.comprehension],
        context: SafeContext,
    ) -> Dict[Any, Any]:
        """Evaluate dict comprehension."""
        result = {}

        def process_generator(gen_idx: int) -> None:
            generator = generators[gen_idx]
            iterable = self._eval_node(generator.iter, context)

            for item in iterable:
                if generator.ifs:
                    if not all(self._eval_node(if_.test, context) for if_ in generator.ifs):
                        continue

                target = generator.target
                if isinstance(target, ast.Name):
                    context._data[target.id] = item

                if gen_idx == len(generators) - 1:
                    k = self._eval_node(key_elt, context)
                    v = self._eval_node(value_elt, context)
                    result[k] = v
                    self._consume_gas(1)
                    if self._gas_used > self._gas_budget:
                        raise GasExceededError(f"Dict comprehension exceeded gas budget")
                else:
                    process_generator(gen_idx + 1)

        process_generator(0)
        return result

    def _eval_call(self, node: ast.Call, context: SafeContext) -> Any:
        """Evaluate function call."""
        func = node.func

        # Get the callable
        if isinstance(func, ast.Name):
            func_name = func.id
            if func_name not in self._builtins:
                raise ASTEvaluatorError(f"Function '{func_name}' is not allowed")
            callable_func = self._builtins[func_name]

        elif isinstance(func, ast.Attribute):
            # Method call like x.split()
            obj = self._eval_node(func.value, context)
            attr_name = func.attr

            if attr_name in DANGEROUS_ATTRIBUTES:
                raise ASTEvaluatorError(f"Attribute '{attr_name}' is not allowed")

            callable_func = getattr(obj, attr_name)

        else:
            raise ASTEvaluatorError("Unsupported function call type")

        # Evaluate arguments
        args = [self._eval_node(arg, context) for arg in node.args]

        # Evaluate keyword arguments
        kwargs = {}
        for kwarg in node.keywords:
            if kwarg.arg:
                kwargs[kwarg.arg] = self._eval_node(kwarg.value, context)

        return callable_func(*args, **kwargs)


# Global evaluator instance
_default_evaluator: Optional[ASTEvaluator] = None


def get_evaluator(
    autonomy_level: int = 1,
    gas_budget: int = 1000,
    max_memory_mb: int = 128,
) -> ASTEvaluator:
    """
    Get the default evaluator instance with trust-based settings.

    Args:
        autonomy_level: Trust level (1=Supervised, 2=Autonomous, 3=Self-Evolving)
        gas_budget: Operations allowed before GasExceededError
        max_memory_mb: Memory limit for SafeContext

    Returns:
        Configured ASTEvaluator instance
    """
    global _default_evaluator
    if _default_evaluator is None:
        _default_evaluator = ASTEvaluator(
            autonomy_level=autonomy_level,
            gas_budget=gas_budget,
            max_memory_mb=max_memory_mb,
        )
    return _default_evaluator


def evaluate_expression(
    expression: str,
    context: Optional[Dict[str, Any]] = None,
    autonomy_level: int = 1,
    gas_budget: int = 1000,
    max_memory_mb: int = 128,
) -> Any:
    """
    Convenience function to evaluate an expression.

    Args:
        expression: Python expression to evaluate
        context: Variables available in the expression
        autonomy_level: Trust level
        gas_budget: Gas budget for the evaluation
        max_memory_mb: SafeContext memory limit

    Returns:
        Result of evaluation
    """
    evaluator = ASTEvaluator(
        autonomy_level=autonomy_level,
        gas_budget=gas_budget,
        max_memory_mb=max_memory_mb,
    )
    return evaluator.evaluate(expression, context)
