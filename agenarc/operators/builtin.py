"""
Built-in Operators

Core operators that are always available:
- Trigger: Entry point for graph execution
- Memory_I/O: Read/write to persistent storage
- Script_Node: Execute inline Python scripts
- Log_Node: Output values for debugging
- Router: Conditional branching
- Loop_Control: Loop iteration control
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port, NodeType, MemoryMode
from agenarc.engine.state import ExecutionContext
from agenarc.engine.evaluator import ASTEvaluator, evaluate_expression


class TriggerOperator(IOperator):
    """
    Trigger operator - entry point for graph execution.

    Generates the initial payload that starts the graph execution.

    Outputs:
        payload: The initial data payload
    """

    @property
    def name(self) -> str:
        return "builtin.trigger"

    @property
    def description(self) -> str:
        return "Entry point trigger for graph execution"

    def get_input_ports(self) -> List[Port]:
        return []

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="payload", type="any", description="Initial payload")
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        # Trigger outputs the initial payload from context
        payload = context.get("payload", {})

        return {
            "payload": payload
        }


class Memory_IO_Operator(IOperator):
    """
    Memory I/O operator - read/write to persistent storage.

    Supports:
    - read: Read value from storage
    - write: Write value to storage
    - delete: Delete value from storage
    - transactional: Write to pending list, commit on success

    Inputs:
        key: Storage key
        value: Value to write (for write mode)

    Outputs:
        value: Read value (for read mode)
        success: Operation success status
    """

    def __init__(self):
        self._storage: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "builtin.memory_io"

    @property
    def description(self) -> str:
        return "Read/write to persistent memory storage with optional transactions"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="key", type="string", description="Storage key"),
            Port(name="value", type="any", description="Value to write", default=None)
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="value", type="any", description="Read value"),
            Port(name="success", type="boolean", description="Operation success")
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        key = inputs.get("key")
        if not key:
            return {"value": None, "success": False}

        # Get node config for transactional setting
        node_config = context.get("_node_config", {})
        transactional = node_config.get("transactional", False)

        # Get the underlying state manager (handles both ExecutionContext and raw StateManager)
        state = getattr(context, '_state', context)

        # Enable transaction mode if configured and not already enabled
        if transactional and not state.in_transaction:
            state.enable_transaction()

        mode = context.get("_memory_mode", MemoryMode.READ.value)

        if mode == MemoryMode.READ.value or mode == "read":
            # In transactional mode, check pending writes first
            if state.in_transaction:
                value = state.get_transactional(key)
                if value is not None or key in state._transactional_pending:
                    return {"value": value, "success": True}
            value = self._storage.get(key)
            return {"value": value, "success": value is not None}

        elif mode == MemoryMode.WRITE.value or mode == "write":
            value = inputs.get("value")

            if state.in_transaction:
                # Add to pending writes (not yet committed)
                state.set_transactional(key, value)
            else:
                # Direct write (original behavior)
                self._storage[key] = value

                # If checkpoint requested, persist to disk
                if context.get("_memory_checkpoint"):
                    self._persist_to_disk(key, value)

            return {"value": value, "success": True}

        elif mode == MemoryMode.DELETE.value or mode == "delete":
            if state.in_transaction:
                # Mark for deletion in pending
                state.set_transactional(key, None)
            else:
                if key in self._storage:
                    del self._storage[key]
            return {"value": None, "success": True}

        return {"value": None, "success": False}

    def _persist_to_disk(self, key: str, value: Any) -> None:
        """Persist value to disk for checkpoint recovery."""
        try:
            storage_dir = Path.home() / ".agenarc" / "storage"
            storage_dir.mkdir(parents=True, exist_ok=True)

            safe_key = key.replace("/", "_").replace("\\", "_")
            file_path = storage_dir / f"{safe_key}.json"

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({"key": key, "value": value}, f)
        except Exception:
            pass  # Fail silently for now



def _autonomy_to_trust_level(autonomy_level: int) -> str:
    """
    Map manifest autonomy level to Script_Node trust level.

    Args:
        autonomy_level: Integer autonomy level (0-3)

    Returns:
        trust_level string: "locked", "trusted", or "developer"
    """
    if autonomy_level <= 1:
        return "locked"
    elif autonomy_level == 2:
        return "trusted"
    else:
        return "developer"


class Script_Node_Operator(IOperator):
    """
    Script Node operator - execute inline Python scripts.

    Allows custom logic to be written directly in the graph without
    requiring a separate plugin.

    Supports:
    - Expression evaluation (returns result)
    - Statement execution (modifies context)

    Inputs:
        script: Python script/expression to execute
        timeout: Timeout in seconds

    Outputs:
        result: Script execution result
        success: Whether execution succeeded
        error: Error message if failed
    """

    def __init__(self):
        self._timeout = 30
        self._evaluator = ASTEvaluator()

    @property
    def name(self) -> str:
        return "builtin.script_node"

    @property
    def description(self) -> str:
        return "Execute inline Python scripts with AST safety"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="script", type="string", description="Python script to execute"),
            Port(name="timeout", type="integer", description="Timeout in seconds", default=30)
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="result", type="any", description="Script execution result"),
            Port(name="success", type="boolean", description="Execution success"),
            Port(name="error", type="string", description="Error message if failed"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        script = inputs.get("script", "")
        timeout = inputs.get("timeout", self._timeout)

        if not script:
            return {"result": None, "success": False, "error": "Empty script"}

        # Get trust level from node config
        # Script_Node is developer-written code, default to developer (fully trusted)
        node_config = context.get("_node_config", {})
        explicit_trust = node_config.get("script_trust_level", None)
        if explicit_trust is not None:
            # Node config explicitly sets trust level
            trust_level = explicit_trust
        else:
            # Default to developer - Script_Node is written by developers, fully trusted
            trust_level = "developer"

        # Get resource limits from manifest permissions
        gas_budget = context.get("_gas_budget", 1000)
        max_memory_mb = context.get("_max_memory_mb", 128)

        # Build evaluation context
        eval_context = self._build_context(context)

        try:
            # Check if it's a single expression or statements
            script_stripped = script.strip()

            # Create evaluator with autonomy level and resource limits
            # Use manifest autonomy level for gas/memory limits, but trust_level controls script access
            manifest_autonomy = context.get("_manifest_autonomy_level", 1)
            evaluator = ASTEvaluator(
                autonomy_level=manifest_autonomy,
                gas_budget=gas_budget,
                max_memory_mb=max_memory_mb,
            )

            # In "locked" mode: only allow AST-based expression evaluation
            if trust_level == "locked":
                if self._is_expression(script_stripped):
                    result = evaluator.evaluate(script_stripped, eval_context)
                    return {"result": result, "success": True, "error": None}
                else:
                    return {
                        "result": None,
                        "success": False,
                        "error": "Script_Node in 'locked' mode only supports expressions. "
                                 "Use 'trusted' or 'developer' mode for statements."
                    }

            # In "trusted" or "developer" mode: allow statements with restrictions
            if self._is_expression(script_stripped):
                result = evaluator.evaluate(script_stripped, eval_context)
                return {"result": result, "success": True, "error": None}
            else:
                # Execute as statements (for context modifications)
                # In "developer" mode, use less restricted globals
                result = await self._execute_statements(
                    script_stripped, context, eval_context,
                    trust_level == "developer"
                )
                return {"result": result, "success": True, "error": None}

        except Exception as e:
            return {"result": None, "success": False, "error": str(e)}

    def _is_expression(self, script: str) -> bool:
        """Check if script is a single expression (not statements)."""
        import ast
        # Simple heuristic: doesn't contain newlines or semicolons
        # and looks like an expression
        if "\n" in script or ";" in script:
            return False
        # Check for common statement keywords
        statement_keywords = ["if ", "for ", "while ", "def ", "class ", "return ", "import ", "try ", "with ", "as ", "assert ", "pass ", "break ", "continue ", "raise ", "yield ", "del ", "global ", "nonlocal "]
        for keyword in statement_keywords:
            if script.startswith(keyword):
                return False
        # Check for assignment operators
        if "=" in script:
            # Might be an assignment - try parsing as expression first
            # If it fails with SyntaxError, it's likely a statement
            try:
                ast.parse(script, mode="eval")
                return True
            except SyntaxError:
                return False
        return True

    def _build_context(self, context: ExecutionContext) -> Dict[str, Any]:
        """Build context dictionary for evaluation."""
        # Get relevant values from execution context
        eval_context = {
            # Access to context values
            "context": context,
            # Loop variables if available
        }

        # Add all context values with prefix
        # This allows expressions like: {{context.my_var}}
        ctx_data = {
            "input": context.get("input"),
            "payload": context.get("payload"),
        }

        # Try to get iteration variables
        loop_id = context.get("_loop_id", "default")
        iteration = context.get(f"_loop_{loop_id}_iteration")
        current_item = context.get(f"_loop_{loop_id}_current_item")
        accumulator = context.get(f"_loop_{loop_id}_accumulator")

        if iteration is not None:
            eval_context["loop"] = {
                "iteration": iteration,
                "current_item": current_item,
                "accumulator": accumulator,
            }

        return eval_context

    async def _execute_statements(
        self,
        script: str,
        context: ExecutionContext,
        eval_context: Dict[str, Any],
        developer_mode: bool = False
    ) -> Any:
        """
        Execute script as statements with context access.

        Args:
            script: Python script to execute
            context: Execution context
            eval_context: Evaluation context
            developer_mode: If True, use less restricted globals (DANGEROUS)
        """
        # Create safe globals for statement execution
        # This is a simplified version - full sandboxing would need more work
        safe_globals = {
            "__builtins__": {
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
                "print": print,
                "json": json,
            },
        }

        # Developer mode: add more builtins (DANGEROUS - only for local development)
        if developer_mode:
            safe_globals["__builtins__"].update({
                "open": open,
                "file": open,
                "input": input,
                "compile": compile,
                "eval": eval,
                "exec": exec,
            })

        # Create a namespace for the script with context access
        script_globals = safe_globals.copy()
        script_globals["_ctx"] = context
        script_globals["_result"] = None

        # Wrap script to capture last expression
        wrapped_script = f"""
{script}
_result = None  # Default
"""

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: exec(wrapped_script, script_globals, {})
        )

        return script_globals.get("_result")


class Log_Node_Operator(IOperator):
    """
    Log Node operator - output values for debugging.

    Simply passes through its input and logs the values.

    Inputs:
        *: Any input values

    Outputs:
        *: Pass through of inputs
    """

    @property
    def name(self) -> str:
        return "builtin.log"

    @property
    def description(self) -> str:
        return "Log and pass through values for debugging"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="message", type="string", description="Log message", default=""),
            Port(name="data", type="any", description="Data to log", default=None)
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="message", type="string", description="Pass through message"),
            Port(name="data", type="any", description="Pass through data")
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        message = inputs.get("message", "")
        data = inputs.get("data")

        # Log to console
        if message or data:
            log_output = f"[AGENARC] {message}" if message else "[AGENARC]"
            if data is not None:
                log_output += f" {data}"
            print(log_output)

        return {
            "message": message,
            "data": data
        }


class Context_Set_Operator(IOperator):
    """
    Context Set operator - set values in global context.

    Inputs:
        key: Context key
        value: Value to set

    Outputs:
        success: Whether the operation succeeded
    """

    @property
    def name(self) -> str:
        return "builtin.context_set"

    @property
    def description(self) -> str:
        return "Set values in global execution context"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="key", type="string", description="Context key"),
            Port(name="value", type="any", description="Value to set")
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="success", type="boolean", description="Operation success")
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        key = inputs.get("key")
        value = inputs.get("value")

        # If key not provided via input, check node config (for output_to_context expansion)
        if not key:
            node_config = context.get("_node_config", {})
            key = node_config.get("_context_key")

        if key:
            context.set(key, value)
            return {"success": True}
        return {"success": False}


class Context_Get_Operator(IOperator):
    """
    Context Get operator - get values from global context.

    Inputs:
        key: Context key
        default: Default value if key not found

    Outputs:
        value: Retrieved value
    """

    @property
    def name(self) -> str:
        return "builtin.context_get"

    @property
    def description(self) -> str:
        return "Get values from global execution context"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="key", type="string", description="Context key"),
            Port(name="default", type="any", description="Default value", default=None)
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="value", type="any", description="Retrieved value")
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        key = inputs.get("key")
        default = inputs.get("default")

        if key:
            value = context.get(key, default)
            return {"value": value}
        return {"value": default}


class Prompt_Builder_Operator(IOperator):
    """
    Prompt Builder operator - manages conversation message history.

    Maintains a messages list in context, appending user/assistant messages
    with safety checks to ensure alternating roles.

    Inputs:
        user: User message to append (mutually exclusive with assistant)
        assistant: Assistant message to append (mutually exclusive with user)

    Outputs:
        messages: The complete messages list

    Config:
        history: Custom history key name (default: node ID, stored as nodes.{history})
        max_history: Maximum number of messages to keep (default: 100)
    """

    def __init__(self):
        self._history_key = None

    @property
    def name(self) -> str:
        return "builtin.prompt_builder"

    @property
    def description(self) -> str:
        return "Build and manage conversation message history"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="user", type="string", description="User message", default=None),
            Port(name="assistant", type="string", description="Assistant message", default=None),
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="messages", type="array", description="Conversation messages list"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        user_msg = inputs.get("user")
        assistant_msg = inputs.get("assistant")

        # Get node config
        node_config = context.get("_node_config", {})
        max_history = node_config.get("max_history", 100)

        # Get node ID for context key
        node_id = context.get("_node_id", "prompt_builder")

        # Determine history key from config or default to node ID
        if self._history_key is None:
            history_name = node_config.get("history", node_id)
            self._history_key = f"nodes.{history_name}"

        # Get existing messages from context
        messages = context.get(self._history_key, [])

        # Safety check: ensure alternating roles
        if messages:
            last_role = messages[-1].get("role")
            if last_role == "user" and user_msg is not None:
                return {"messages": messages, "error": "Cannot add user message after user (alternation violation)"}
            if last_role == "assistant" and assistant_msg is not None:
                return {"messages": messages, "error": "Cannot add assistant message after assistant (alternation violation)"}

        # Append the appropriate message
        if user_msg is not None:
            messages.append({"role": "user", "content": user_msg})
        elif assistant_msg is not None:
            messages.append({"role": "assistant", "content": assistant_msg})

        # Trim to max_history (keep oldest messages)
        if len(messages) > max_history:
            messages = messages[-max_history:]

        # Store back to context
        context.set(self._history_key, messages)

        return {"messages": messages}


# Registry of all built-in operators
BUILTIN_OPERATORS: Dict[str, type] = {
    "Trigger": TriggerOperator,
    "Memory_I/O": Memory_IO_Operator,
    "Script_Node": Script_Node_Operator,
    "Log": Log_Node_Operator,
    "Prompt_Builder": Prompt_Builder_Operator,
    "Context_Set": Context_Set_Operator,
    "Context_Get": Context_Get_Operator,
    "Join": None,  # Loaded from join.py
    "Router": None,  # Loaded from router.py
    "Loop_Control": None,  # Loaded from loop.py
    "LLM_Task": None,  # Loaded from llm.py
}


def _register_llm_operators():
    """Register LLM operators from llm.py."""
    try:
        from agenarc.operators.llm import LLM_Task_Operator
        BUILTIN_OPERATORS["LLM_Task"] = LLM_Task_Operator
    except ImportError:
        pass  # LLM operators not available


def _register_router_operator():
    """Register Router operator from router.py."""
    try:
        from agenarc.operators.router import RouterOperator
        BUILTIN_OPERATORS["Router"] = RouterOperator
    except ImportError:
        pass  # Router not available


def _register_loop_operator():
    """Register Loop_Control operator from loop.py."""
    try:
        from agenarc.operators.loop import Loop_Control_Operator
        BUILTIN_OPERATORS["Loop_Control"] = Loop_Control_Operator
    except ImportError:
        pass  # Loop_Control not available


def _register_join_operator():
    """Register Join operator from join.py."""
    try:
        from agenarc.operators.join import JoinOperator
        BUILTIN_OPERATORS["Join"] = JoinOperator
    except ImportError:
        pass  # Join not available


def _register_evolution_operators():
    """Register evolution operators (Asset_Reader, Asset_Writer, Runtime_Reload)."""
    try:
        from agenarc.operators.evolution import get_evolution_operators
        evolution_ops = get_evolution_operators()
        for name, op_class in evolution_ops.items():
            BUILTIN_OPERATORS[name] = op_class
    except ImportError:
        pass  # Evolution operators not available


# Auto-register operators on import
_register_llm_operators()
_register_router_operator()
_register_loop_operator()
_register_join_operator()
_register_evolution_operators()


def get_builtin_operator(node_type: str) -> Optional[IOperator]:
    """
    Get a built-in operator instance by node type.

    Args:
        node_type: Node type string

    Returns:
        Operator instance or None
    """
    operator_class = BUILTIN_OPERATORS.get(node_type)
    if operator_class:
        return operator_class()
    return None
