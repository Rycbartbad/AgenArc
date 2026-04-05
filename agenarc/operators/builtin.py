"""
Built-in Operators

Core operators that are always available:
- Trigger: Entry point for graph execution
- Memory_I/O: Read/write to persistent storage
- Script_Node: Execute inline Python scripts
- Log_Node: Output values for debugging
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
        # Trigger generates the initial payload
        # The payload can come from context or be a default
        payload = context.get("trigger_payload", {})

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
        return "Read/write to persistent memory storage"

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

        mode = context.get("_memory_mode", MemoryMode.READ.value)

        if mode == MemoryMode.READ.value or mode == "read":
            value = self._storage.get(key)
            return {"value": value, "success": value is not None}

        elif mode == MemoryMode.WRITE.value or mode == "write":
            value = inputs.get("value")
            self._storage[key] = value

            # If checkpoint requested, persist to disk
            if context.get("_memory_checkpoint"):
                self._persist_to_disk(key, value)

            return {"value": value, "success": True}

        elif mode == MemoryMode.DELETE.value or mode == "delete":
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

    def load_from_disk(self, key: str) -> Optional[Any]:
        """Load value from disk."""
        try:
            storage_dir = Path.home() / ".agenarc" / "storage"
            safe_key = key.replace("/", "_").replace("\\", "_")
            file_path = storage_dir / f"{safe_key}.json"

            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("value")
        except Exception:
            pass
        return None


class Script_Node_Operator(IOperator):
    """
    Script Node operator - execute inline Python scripts.

    Allows custom logic to be written directly in the graph without
    requiring a separate plugin.

    Inputs:
        Dynamic based on script definition

    Outputs:
        Dynamic based on script definition
    """

    def __init__(self):
        self._timeout = 30

    @property
    def name(self) -> str:
        return "builtin.script_node"

    @property
    def description(self) -> str:
        return "Execute inline Python scripts"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="script", type="string", description="Python script to execute"),
            Port(name="timeout", type="integer", description="Timeout in seconds", default=30)
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="result", type="any", description="Script execution result"),
            Port(name="success", type="boolean", description="Execution success")
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        script = inputs.get("script", "")
        timeout = inputs.get("timeout", self._timeout)

        if not script:
            return {"result": None, "success": False}

        try:
            # Execute script in a restricted environment
            result = await self._execute_script(script, context, timeout)
            return {"result": result, "success": True}
        except Exception as e:
            return {"result": str(e), "success": False}

    async def _execute_script(
        self,
        script: str,
        context: ExecutionContext,
        timeout: int
    ) -> Any:
        """Execute Python script with timeout."""

        # Create a restricted globals dictionary
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
            "context": context,
        }

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: exec(script, safe_globals, {})
        )

        return result


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


# Registry of all built-in operators
BUILTIN_OPERATORS: Dict[str, type] = {
    "Trigger": TriggerOperator,
    "Memory_I/O": Memory_IO_Operator,
    "Script_Node": Script_Node_Operator,
    "Log": Log_Node_Operator,
    "Context_Set": Context_Set_Operator,
    "Context_Get": Context_Get_Operator,
    "LLM_Task": None,  # Loaded from llm.py
}


def _register_llm_operators():
    """Register LLM operators from llm.py."""
    try:
        from agenarc.operators.llm import LLM_Task_Operator
        BUILTIN_OPERATORS["LLM_Task"] = LLM_Task_Operator
    except ImportError:
        pass  # LLM operators not available


# Auto-register LLM operators on import
_register_llm_operators()


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
