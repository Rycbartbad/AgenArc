"""
SubGraph Operator for AgenArc

Executes a nested .agrc agent as a sub-graph with isolated context.
Ports are auto-resolved by the ProtocolLoader from the child bundle.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agenarc.engine.executor import ExecutionEngine
    from agenarc.engine.state import ExecutionContext

from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port


class SubGraphError(Exception):
    """Raised when SubGraph execution fails."""

    pass


class SubGraphOperator(IOperator):
    """
    SubGraph Operator — execute a nested .agrc agent as a sub-graph.

    The child agent runs in an isolated context with its own StateManager.
    Only terminal node outputs are returned to the parent graph.
    Ports are auto-resolved by the ProtocolLoader during graph loading.
    """

    def __init__(self) -> None:
        self._input_ports: list[Port] = []
        self._output_ports: list[Port] = []

    @property
    def name(self) -> str:
        return "builtin.subgraph"

    @property
    def description(self) -> str:
        return "Execute a nested .agrc agent as a sub-graph with isolated context"

    def get_input_ports(self) -> list[Port]:
        return self._input_ports

    def get_output_ports(self) -> list[Port]:
        return self._output_ports

    async def execute(self, inputs: dict[str, Any], context: "ExecutionContext") -> dict[str, Any]:
        # 1. Get bundle path from node config
        node_config = context.get("_node_config", {})
        bundle_ref = node_config.get("bundle", "")
        if not bundle_ref:
            raise SubGraphError("No bundle specified in SubGraph node config")

        # 2. Resolve bundle path relative to parent bundle
        parent_bundle_path = context.get("_bundle_path")
        if parent_bundle_path:
            parent_dir = Path(str(parent_bundle_path))
            if not parent_dir.is_dir():
                parent_dir = parent_dir.parent
            child_path = parent_dir / bundle_ref
        else:
            child_path = Path(bundle_ref)

        if not child_path.exists():
            raise SubGraphError(f"Bundle not found: {bundle_ref}")

        # 3. Create child ExecutionEngine with isolated state
        from agenarc.engine.executor import ExecutionEngine, ExecutionMode
        from agenarc.operators.builtin import BUILTIN_OPERATORS

        child_engine = ExecutionEngine()

        # 4. Set bundle path for VFS resolution
        if child_path.is_dir():
            child_engine.set_bundle_path(child_path)
        else:
            child_engine.set_bundle_path(child_path.parent)

        # 5. Load child manifest for permissions
        if child_path.is_dir():
            manifest_path = child_path / "manifest.json"
            if manifest_path.exists():
                child_engine.load_manifest(manifest_path)

        # 6. Register built-in operators (supports nested SubGraph)
        for node_type, op_class in BUILTIN_OPERATORS.items():
            if op_class is not None:
                child_engine.register_builtin_operator(node_type, op_class)

        # 7. Load child protocol
        child_engine.load_protocol(str(child_path))

        # 8. Run child with mode="sync"
        result = await child_engine.execute(initial_inputs=inputs, mode=ExecutionMode.SYNC)

        # 9. Handle child failure
        if result.status == "failed":
            error = result.error or Exception("SubGraph execution failed")
            raise SubGraphError(f"SubGraph execution failed: {error}") from error

        # 10. Collect terminal node outputs with port name collision handling
        return self._collect_terminal_outputs(child_engine)

    def _collect_terminal_outputs(self, engine: "ExecutionEngine") -> dict[str, Any]:
        """Collect outputs from terminal nodes of child graph."""
        graph = engine.graph
        if not graph:
            return {}

        state = engine.state
        if not state:
            return {}

        # Find terminal nodes (nodes with no outgoing data edges)
        terminal_node_ids: list[str] = []
        for node in graph.nodes:
            outgoing = graph.get_outgoing_edges(node.id)
            data_outgoing = [e for e in outgoing if e.sourcePort]
            if not data_outgoing:
                terminal_node_ids.append(node.id)

        # Count port name occurrences for collision detection
        port_name_counts: dict[str, int] = {}
        node_ports: dict[str, dict[str, Any]] = {}
        for node_id in terminal_node_ids:
            node_outputs = state.get_node_outputs(node_id)
            if not node_outputs:
                continue
            node_ports[node_id] = node_outputs
            for port_name in node_outputs:
                port_name_counts[port_name] = port_name_counts.get(port_name, 0) + 1

        # Build outputs with collision handling
        outputs: dict[str, Any] = {}
        for node_id, node_outputs in node_ports.items():
            for port_name, value in node_outputs.items():
                if port_name_counts.get(port_name, 0) > 1:
                    outputs[f"{node_id}.{port_name}"] = value
                else:
                    outputs[port_name] = value

        return outputs
