"""
Evaluator — backward-compatible re-exports.

Sourced from two independent submodules:
  - ast_evaluator.py:   AST safe expression evaluator (Script_Node)
  - template_resolver.py:  {{key}} template + VFS path resolver (all nodes)
"""

from agenarc.engine.ast_evaluator import (
    DANGEROUS_ATTRIBUTES,
    ASTEvaluator,
    ASTEvaluatorError,
    GasExceededError,
    MemoryLimitError,
    SafeContext,
    evaluate_expression,
)
from agenarc.engine.template_resolver import (
    TemplateError,
    resolve_template,
    resolve_template_any,
    resolve_template_dict,
    resolve_vfs_and_template,
    resolve_vfs_path,
)

__all__ = [
    "ASTEvaluatorError", "GasExceededError", "MemoryLimitError",
    "DANGEROUS_ATTRIBUTES", "SafeContext", "ASTEvaluator", "evaluate_expression",
    "TemplateError",
    "resolve_template", "resolve_template_dict", "resolve_template_any",
    "resolve_vfs_path", "resolve_vfs_and_template",
]
