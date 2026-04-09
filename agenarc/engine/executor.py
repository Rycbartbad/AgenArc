"""
Execution Engine

Core execution engine for AgenArc directed-graph Agent orchestration.

Architecture:
    ExecutionEngine
    ├── Loader (Graph parsing)
    ├── Scheduler (Control flow scheduling)
    ├── Executor (Node execution)
    ├── PluginManager (Operator loading)
    └── StateManager (Context + Checkpoint)
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from agenarc.protocol.loader import ProtocolLoader
from agenarc.protocol.schema import (
    AutonomyLevel,
    Edge,
    ErrorHandling,
    ErrorStrategy,
    Graph,
    Node,
    NodeType,
    Permissions,
)
from agenarc.graph.traversal import GraphTraversal
from agenarc.engine.state import StateManager, ExecutionContext
from agenarc.engine.evaluator import resolve_vfs_and_template

if TYPE_CHECKING:
    from agenarc.plugins.manager import PluginManager
    from agenarc.operators.operator import IOperator


class NodeStatus(Enum):
    """Node execution status."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()
    WAITING = auto()


class ExecutionMode(Enum):
    """Execution mode."""
    SYNC = auto()
    ASYNC = auto()
    PARALLEL = auto()


@dataclass
class ExecutionResult:
    """Result of a node execution."""
    node_id: str
    status: NodeStatus
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None
    duration_ms: float = 0


@dataclass
class GraphResult:
    """Result of a complete graph execution."""
    execution_id: str
    status: str  # "success", "failed", "partial"
    node_results: Dict[str, ExecutionResult] = field(default_factory=dict)
    final_outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None
    duration_ms: float = 0


class ExecutionEngine:
    """
    Core execution engine for directed-graph Agent orchestration.

    Loads protocol, parses graph, and executes nodes in topological order
    with support for:
    - Sequential and parallel execution
    - Error handling and retry
    - Checkpoint and resume
    - Custom operators via PluginManager

    Usage:
        engine = ExecutionEngine(plugin_manager)
        engine.load_protocol("flow.json")
        result = await engine.execute()
    """

    def __init__(
        self,
        plugin_manager: Optional["PluginManager"] = None,
        max_parallel: int = 4,
        enable_checkpoint: bool = True,
    ):
        self.plugin_manager = plugin_manager
        self.max_parallel = max_parallel
        self.enable_checkpoint = enable_checkpoint

        # Internal state
        self._graph: Optional[Graph] = None
        self._traversal: Optional[GraphTraversal] = None
        self._state: Optional[StateManager] = None
        self._operators: Dict[str, "IOperator"] = {}
        self._adjacency: Dict[str, List[str]] = {}  # For loop support

        # Manifest permissions (for Trust-based Autonomy)
        self._permissions: Permissions = Permissions()

        # Bundle path for VFS resolution
        self._bundle_path: Optional[Any] = None

        # Execution tracking
        self._node_statuses: Dict[str, NodeStatus] = {}
        self._node_errors: Dict[str, Exception] = {}
        self._execution_id: str = ""

        # Built-in operators registry
        self._builtin_operators: Dict[str, type] = {}

        # Running flag
        self._running: bool = False

    def load_manifest(self, manifest_path: Any) -> None:
        """
        Load manifest.json from .agrc bundle.

        Args:
            manifest_path: Path to manifest.json or .agrc bundle directory
        """
        import json
        from pathlib import Path

        manifest_path = Path(manifest_path)

        # If it's a directory, look for manifest.json inside
        if manifest_path.is_dir():
            manifest_file = manifest_path / "manifest.json"
        else:
            manifest_file = manifest_path

        if not manifest_file.exists():
            return  # Use defaults

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            permissions_data = data.get("permissions", {})
            self._permissions = Permissions(
                allow_script_read=permissions_data.get("allow_script_read", True),
                allow_script_write=permissions_data.get("allow_script_write", False),
                allow_prompt_read=permissions_data.get("allow_prompt_read", True),
                allow_prompt_write=permissions_data.get("allow_prompt_write", False),
                allow_flow_modification=permissions_data.get("allow_flow_modification", False),
                allow_manifest_modification=permissions_data.get("allow_manifest_modification", False),
                allowed_modules=permissions_data.get("allowed_modules", []),
                autonomy_level=AutonomyLevel(
                    permissions_data.get("autonomy_level", "level_1")
                ),
                gas_budget=permissions_data.get("gas_budget", 1000),
                max_memory_mb=permissions_data.get("max_memory_mb", 128),
            )
        except Exception:
            pass  # Use defaults on error

    def register_builtin_operator(
        self,
        node_type: str,
        operator_class: type
    ) -> None:
        """
        Register a built-in operator class for a node type.

        Args:
            node_type: Node type string this operator handles
            operator_class: Operator class
        """
        self._builtin_operators[node_type] = operator_class

    def set_bundle_path(self, bundle_path: Any) -> None:
        """
        Set the bundle path for VFS resolution.

        Args:
            bundle_path: Path to the .agrc bundle directory
        """
        self._bundle_path = bundle_path

    def load_protocol(
        self,
        source: Any,
        validate: bool = True
    ) -> None:
        """
        Load and validate a protocol.

        Args:
            source: File path or dict containing protocol
            validate: Whether to validate against schema

        Raises:
            LoaderError: If loading fails
            SchemaValidationError: If validation fails
        """
        loader = ProtocolLoader(validate=validate)
        self._graph = loader.load(source)
        self._traversal = GraphTraversal(self._graph)

        # Build adjacency list for loop support
        self._adjacency = {node.id: [] for node in self._graph.nodes}
        entry_point = self._graph.entryPoint
        for edge in self._graph.edges:
            # Skip edges pointing to entry point - they create cycles
            # Entry point is always executed first, ignoring incoming edges
            if edge.target == entry_point:
                continue
            if edge.source in self._adjacency:
                self._adjacency[edge.source].append(edge.target)

        # Validate graph structure
        errors = self._traversal.validate()
        if errors:
            raise ValueError(f"Graph validation errors: {', '.join(errors)}")

        # Reset execution state
        self._node_statuses = {
            node.id: NodeStatus.PENDING for node in self._graph.nodes
        }
        self._node_errors = {}

    def get_operator(self, node: Node) -> Optional["IOperator"]:
        """
        Get operator for a node.

        Args:
            node: Node to get operator for

        Returns:
            Operator instance or None
        """
        # Plugin node type - always use plugin manager
        if node.type == NodeType.PLUGIN:
            if self.plugin_manager:
                config = node.metadata.get("config", {})
                plugin_name = config.get("plugin", "")
                function_name = config.get("function", "")
                if plugin_name and function_name:
                    return self.plugin_manager.get_operator(plugin_name, function_name)
            return None

        # Check built-in operators first
        if node.type.value in self._builtin_operators:
            operator_class = self._builtin_operators[node.type.value]
            return operator_class()

        # Check plugin manager for unknown types (backward compatibility)
        if self.plugin_manager:
            config = node.metadata.get("config", {})
            plugin_name = config.get("plugin", "builtin")
            function_name = config.get("function", "")
            return self.plugin_manager.get_operator(plugin_name, function_name)

        return None

    async def execute(
        self,
        initial_inputs: Dict[str, Any] = None,
        mode: ExecutionMode = ExecutionMode.ASYNC
    ) -> GraphResult:
        """
        Execute the loaded graph.

        Args:
            initial_inputs: Initial input values to set in context
            mode: Execution mode (sync/async/parallel)

        Returns:
            GraphResult with execution results

        Raises:
            RuntimeError: If no graph is loaded
        """
        if not self._graph:
            raise RuntimeError("No graph loaded. Call load_protocol() first.")

        # Initialize execution
        self._execution_id = str(uuid.uuid4())
        # Reuse existing state if already set (e.g., from REPL session)
        if self._state is None:
            self._state = StateManager(auto_checkpoint=self.enable_checkpoint)
            self._state.initialize(self._execution_id, self._graph.entryPoint or "unknown")

        # Seed initial inputs
        if initial_inputs:
            for key, value in initial_inputs.items():
                self._state.set_global(key, value)

        # Set manifest autonomy level for Script_Node operators
        autonomy_value = 1
        if self._permissions.autonomy_level == AutonomyLevel.LEVEL_2_AUTONOMOUS:
            autonomy_value = 2
        elif self._permissions.autonomy_level == AutonomyLevel.LEVEL_3_SELF_EVOLVING:
            autonomy_value = 3
        self._state.set_global("_manifest_autonomy_level", autonomy_value)
        self._state.set_global("_gas_budget", self._permissions.gas_budget)
        self._state.set_global("_max_memory_mb", self._permissions.max_memory_mb)

        # Set bundle path for VFS resolution
        if self._bundle_path:
            self._state.set_global("_bundle_path", self._bundle_path)
            # Convert permissions to dict if it's a Permissions object
            perms = self._permissions
            if hasattr(perms, 'allow_script_read'):
                perms = {
                    "allow_script_read": perms.allow_script_read,
                    "allow_script_write": perms.allow_script_write,
                    "allow_prompt_read": perms.allow_prompt_read,
                    "allow_prompt_write": perms.allow_prompt_write,
                }
            self._state.set_global("_vfs_permissions", perms)

        # Get entry point
        entry_node = self._graph.get_node(self._graph.entryPoint)
        if not entry_node:
            raise ValueError(f"Entry point '{self._graph.entryPoint}' not found")

        # Track execution
        self._running = True
        start_time = asyncio.get_event_loop().time()

        try:
            # Execute from entry point
            if mode == ExecutionMode.ASYNC:
                await self._execute_async(entry_node)
            elif mode == ExecutionMode.PARALLEL:
                await self._execute_parallel(entry_node)
            else:
                await self._execute_sync(entry_node)

            # Commit transactional Memory_I/O if any
            if self._state.in_transaction:
                self._state.commit_transaction()

        except Exception as e:
            # Rollback transactional Memory_I/O on failure
            if self._state.in_transaction:
                self._state.rollback_transaction()

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            return GraphResult(
                execution_id=self._execution_id,
                status="failed",
                node_results=self._build_node_results(),
                error=e,
                duration_ms=duration_ms
            )

        finally:
            self._running = False

        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        # Determine overall status
        has_failed = any(s == NodeStatus.FAILED for s in self._node_statuses.values())
        has_skipped = any(s == NodeStatus.SKIPPED for s in self._node_statuses.values())

        if has_failed:
            status = "failed"
            # Rollback on failure even if committed above
            if self._state.in_transaction:
                self._state.rollback_transaction()
        elif has_skipped:
            status = "partial"
        else:
            status = "success"

        return GraphResult(
            execution_id=self._execution_id,
            status=status,
            node_results=self._build_node_results(),
            final_outputs=self._collect_final_outputs(),
            duration_ms=duration_ms
        )

    async def _execute_sync(self, entry_node: Node) -> None:
        """
        Synchronous execution (sequential).

        Args:
            entry_node: Entry point node
        """
        execution_order = self._traversal.get_execution_order(entry_node.id)

        for node_id in execution_order:
            node = self._graph.get_node(node_id)
            if node:
                await self._execute_node(node)

    async def _execute_async(self, entry_node: Node) -> None:
        """
        Async execution with dependency tracking.

        Supports Router-based loops where Router can route to previously
        executed nodes, forming a cycle.

        Args:
            entry_node: Entry point node
        """
        executed: Set[str] = set()
        pending: Set[str] = {
            node.id for node in self._graph.nodes
        }

        while pending and self._running:
            # Find nodes ready to execute
            ready = self._traversal.get_ready_nodes(executed, pending)

            if not ready:
                if pending:
                    remaining = list(pending)
                    raise RuntimeError(
                        f"Deadlock detected. Remaining nodes: {remaining}"
                    )
                break

            # Execute ready nodes
            for node_id in ready:
                node = self._graph.get_node(node_id)
                if not node:
                    continue

                # Execute the node
                outputs = await self._execute_node_with_tracking(node)

                # Handle Router routing
                # Router's _selected output is a sourcePort label to match in edges
                # (like assembly jump target: "loop", "exit", "A", "B", or node_id)
                if node.type.value == "Router" and outputs:
                    selected = outputs.get("_selected")
                    if selected:
                        # Find edge with matching sourcePort
                        routing_target = self._find_routing_target(node_id, selected)
                        if routing_target:
                            # If target was already executed, this creates a loop
                            # Remove from executed to allow re-execution
                            if routing_target in executed:
                                executed.discard(routing_target)
                            pending.add(routing_target)

                # Normal completion
                executed.add(node_id)
                pending.discard(node_id)

    def _find_routing_target(self, source_node_id: str, source_port: str) -> Optional[str]:
        """
        Find the target node for a Router output.

        Matches edge with sourcePort = source_port to determine
        which node to execute next (like assembly jump target).

        Args:
            source_node_id: Source node (Router) ID
            source_port: The sourcePort label to match

        Returns:
            Target node ID, or None if not found
        """
        for edge in self._graph.edges:
            if edge.source == source_node_id and edge.sourcePort == source_port:
                return edge.target
        return None

    def _topological_sort_subset(
        self,
        node_ids: Set[str],
        exclude: Set[str]
    ) -> List[str]:
        """
        Topological sort of a subset of nodes.

        Args:
            node_ids: Set of node IDs to sort
            exclude: Node IDs to exclude from ordering

        Returns:
            List of node IDs in topological order
        """
        # Build subgraph
        subgraph_adj = {
            n: [t for t in self._adjacency.get(n, []) if t in node_ids and t not in exclude]
            for n in node_ids
        }

        in_degree = {n: 0 for n in node_ids if n not in exclude}
        for n in node_ids:
            if n in exclude:
                continue
            for succ in subgraph_adj.get(n, []):
                if succ in in_degree:
                    in_degree[succ] += 1

        queue = [n for n in node_ids if n not in exclude and in_degree.get(n, 0) == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            for succ in subgraph_adj.get(node_id, []):
                if succ in in_degree:
                    in_degree[succ] -= 1
                    if in_degree[succ] == 0:
                        queue.append(succ)

        return result

    async def _execute_parallel(self, entry_node: Node) -> None:
        """
        Parallel execution with concurrency limiting.

        Args:
            entry_node: Entry point node
        """
        semaphore = asyncio.Semaphore(self.max_parallel)
        executed: Set[str] = set()
        pending: Set[str] = {
            node.id for node in self._graph.nodes
        }

        async def execute_with_semaphore(node: Node) -> None:
            async with semaphore:
                await self._execute_node(node)
                executed.add(node.id)
                pending.discard(node.id)

        tasks = []

        while pending and self._running:
            ready = self._traversal.get_ready_nodes(executed, pending)

            if not ready:
                if pending:
                    remaining = list(pending)
                    raise RuntimeError(
                        f"Deadlock detected. Remaining nodes: {remaining}"
                    )
                break

            # Launch parallel tasks
            for node_id in ready:
                node = self._graph.get_node(node_id)
                if node:
                    task = asyncio.create_task(execute_with_semaphore(node))
                    tasks.append(task)

            # Wait for current batch
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []

    async def _execute_node(self, node: Node) -> None:
        """
        Execute a single node.

        Args:
            node: Node to execute
        """
        await self._execute_node_with_tracking(node)

    async def _execute_node_with_tracking(self, node: Node) -> Optional[Dict[str, Any]]:
        """
        Execute a single node and return outputs.

        Used by async executor with loop support.

        Args:
            node: Node to execute

        Returns:
            Node outputs dict, or None if node has no operator
        """
        context = ExecutionContext(self._state)

        # Check for checkpoint restoration
        if self.enable_checkpoint:
            checkpoint_key = f"checkpoint_{node.id}"
            saved_checkpoint = context.get(checkpoint_key)
            if saved_checkpoint:
                self._state.restore(saved_checkpoint)

        # Update status
        self._node_statuses[node.id] = NodeStatus.RUNNING

        # Get operator
        operator = self.get_operator(node)

        if not operator:
            # No operator found, mark as completed with no outputs
            self._node_statuses[node.id] = NodeStatus.COMPLETED
            return None

        # Create context getter for template resolution
        def context_getter(key: str) -> Any:
            return self._state.get_global(key)

        # Create bundle path getter for VFS resolution
        def bundle_path_getter() -> Any:
            return self._state.get_global("_bundle_path")

        # Create permissions getter
        def permissions_getter() -> Any:
            return self._state.get_global("_vfs_permissions")

        # Resolve inputs (templates resolved at execution time for freshness)
        inputs = self._resolve_inputs(node)
        inputs = resolve_vfs_and_template(
            inputs, context_getter, bundle_path_getter, permissions_getter(), allow_missing=True
        )

        # Set node config in context for operators to access
        # Templates in config are resolved at execution time
        node_config = node.metadata.get("config", {})
        node_config = resolve_vfs_and_template(
            node_config, context_getter, bundle_path_getter, permissions_getter(), allow_missing=True
        )
        context.set("_node_type", node.type.value)
        context.set("_node_config", node_config)

        # Create checkpoint before execution
        if self.enable_checkpoint and node.checkpoint:
            checkpoint_id = self._state.checkpoint(f"pre_{node.id}")
            context.set(f"checkpoint_{node.id}", checkpoint_id)

        try:
            # Execute operator
            outputs = await self._safe_execute(operator, inputs, context)

            # Store outputs
            self._state.store_output(node.id, outputs)

            # Check for in-place mutations in strict mode
            context.post_node_execute(node.id)

            # Update status
            self._node_statuses[node.id] = NodeStatus.COMPLETED

            return outputs

        except Exception as e:
            await self._handle_node_error(node, e, context)
            return None

    async def _safe_execute(
        self,
        operator: "IOperator",
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Safely execute operator with timeout.

        Args:
            operator: Operator to execute
            inputs: Input values
            context: Execution context

        Returns:
            Operator outputs
        """
        timeout = 300  # 5 minutes default

        try:
            result = await asyncio.wait_for(
                operator.execute(inputs, context),
                timeout=timeout
            )
            return result or {}
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operator execution timed out after {timeout}s")

    async def _handle_node_error(
        self,
        node: Node,
        error: Exception,
        context: ExecutionContext
    ) -> None:
        """
        Handle node execution error.

        Args:
            node: Node that failed
            error: Exception that occurred
            context: Execution context
        """
        self._node_errors[node.id] = error
        self._node_statuses[node.id] = NodeStatus.FAILED

        error_handling = node.errorHandling

        if not error_handling:
            # No local error handling configured
            # Check for global error node
            if self._graph and self._graph.errorNode:
                # Execute global error handler
                error_node = self._graph.get_node(self._graph.errorNode)
                if error_node:
                    # Set error info in context for the error handler
                    context.set("_error_node_id", node.id)
                    context.set("_error_message", str(error))
                    context.set("_error_type", type(error).__name__)
                    await self._execute_node(error_node)
                    return
            # Default to ABORT if no error handling configured
            # This prevents silent swallowing of errors
            raise error

        strategy = error_handling.strategy

        if strategy == ErrorStrategy.RETRY:
            max_retries = error_handling.maxRetries
            retry_count = context.get(f"retry_{node.id}", 0)

            if retry_count < max_retries:
                context.set(f"retry_{node.id}", retry_count + 1)
                # Retry the node
                await self._execute_node(node)
            else:
                # Max retries exceeded
                await self._handle_fallback(node, error_handling, context)

        elif strategy == ErrorStrategy.FALLBACK:
            await self._handle_fallback(node, error_handling, context)

        elif strategy == ErrorStrategy.SKIP:
            self._node_statuses[node.id] = NodeStatus.SKIPPED

        elif strategy == ErrorStrategy.ABORT:
            # Re-raise to abort execution
            raise error

    async def _handle_fallback(
        self,
        node: Node,
        error_handling: ErrorHandling,
        context: ExecutionContext
    ) -> None:
        """
        Handle fallback for a failed node.

        Args:
            node: Failed node
            error_handling: Error handling configuration
            context: Execution context
        """
        if error_handling.fallbackNode:
            fallback = self._graph.get_node(error_handling.fallbackNode)
            if fallback:
                # Store error info in context before fallback execution
                self._state.store_output(node.id, {"_error": str(self._node_errors[node.id])})
                await self._execute_node(fallback)

    def _resolve_inputs(self, node: Node) -> Dict[str, Any]:
        """
        Resolve node inputs from upstream outputs and context.

        Reads from context using the key format: nodes.{source_node_id}.{sourcePort}

        Args:
            node: Node to resolve inputs for

        Returns:
            Dictionary of input values
        """
        inputs = {}

        # Find edges pointing to this node
        incoming = self._graph.get_incoming_edges(node.id)

        for edge in incoming:
            # Skip edges without sourcePort - they exist for control flow only (e.g., edges to trigger)
            if not edge.sourcePort:
                continue

            # Read from context using namespaced key
            key = f"nodes.{edge.source}.{edge.sourcePort}"
            value = self._state.get_global(key)

            if edge.targetPort:
                inputs[edge.targetPort] = value
            else:
                # If no target port specified, use source port name as key
                inputs[edge.sourcePort] = value

        # Fill in defaults from port definitions
        for port in node.inputs:
            if port.name not in inputs and port.default is not None:
                inputs[port.name] = port.default

        return inputs

    def _build_node_results(self) -> Dict[str, ExecutionResult]:
        """Build node results dictionary."""
        results = {}
        for node_id, status in self._node_statuses.items():
            outputs = self._state.get_node_outputs(node_id) if self._state else {}
            results[node_id] = ExecutionResult(
                node_id=node_id,
                status=status,
                outputs=outputs,
                error=self._node_errors.get(node_id)
            )
        return results

    def _collect_final_outputs(self) -> Dict[str, Any]:
        """Collect final outputs from terminal nodes."""
        # Find nodes with no outgoing edges (terminal nodes)
        terminal_node_ids = set()
        for node in self._graph.nodes:
            outgoing = self._graph.get_outgoing_edges(node.id)
            if not outgoing:
                terminal_node_ids.add(node.id)

        # Collect outputs from terminal nodes
        final = {}
        for node_id in terminal_node_ids:
            outputs = self._state.get_node_outputs(node_id) if self._state else {}
            final[node_id] = outputs

        return final

    def stop(self) -> None:
        """Stop the running execution."""
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if execution is running."""
        return self._running

    @property
    def graph(self) -> Optional[Graph]:
        """Get the loaded graph."""
        return self._graph

    @property
    def state(self) -> Optional[StateManager]:
        """Get the state manager."""
        return self._state
