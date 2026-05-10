"""
Protocol Loader

Loads and parses AgenArc protocol JSON files into Graph objects.
Supports both standalone flow.json and .agrc bundle format.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_jsonschema_available = None  # None = not checked, True/False = result

from agenarc.protocol.schema import (
    AGENARC_SCHEMA,
    Condition,
    ConditionOperator,
    Edge,
    ErrorHandling,
    ErrorStrategy,
    Graph,
    MemoryMode,
    Node,
    NodeConfig,
    NodeType,
    Port,
    TriggerSource,
)


class LoaderError(Exception):
    """Raised when protocol loading fails."""

    pass


class SchemaValidationError(LoaderError):
    """Raised when JSON does not match the schema."""

    pass


class ProtocolLoader:
    """
    Loads and validates AgenArc protocol JSON files.

    Usage:
        loader = ProtocolLoader()
        graph = loader.load("path/to/flow.json")
    """

    def __init__(self, validate: bool = True):
        self.validate = validate
        self._node_types = {t.value: t for t in NodeType}
        self._error_strategies = {s.value: s for s in ErrorStrategy}
        self._trigger_sources = {s.value: s for s in TriggerSource}
        self._memory_modes = {m.value: m for m in MemoryMode}
        self._condition_operators = {o.value: o for o in ConditionOperator}
        # Path of the bundle currently being loaded for SubGraph port resolution
        self._parent_path: Path | None = None
        # Stack of bundle paths being resolved for recursive reference detection
        self._resolving_stack: list[str] = []

    def load(self, source: str | Path | dict[str, Any]) -> Graph:
        """
        Load protocol from file path or dictionary.

        Args:
            source: File path (str/Path) or dict containing protocol data

        Returns:
            Graph object

        Raises:
            LoaderError: If loading or parsing fails
            SchemaValidationError: If validation is enabled and schema doesn't match
        """
        if isinstance(source, (str, Path)):
            return self.load_file(source)
        elif isinstance(source, dict):
            return self.load_dict(source)
        else:
            raise LoaderError(f"Unsupported source type: {type(source)}")

    def load_file(self, path: str | Path) -> Graph:
        """
        Load protocol from a JSON file or bundle directory.

        Args:
            path: Path to flow.json, .agrc bundle, or bundle directory

        Returns:
            Graph object
        """
        path = Path(path)

        if not path.exists():
            raise LoaderError(f"File not found: {path}")

        # Set parent path for SubGraph bundle resolution
        if path.is_dir():
            self._parent_path = path
        elif path.suffix in (".json", ".agrc"):
            self._parent_path = path.parent

        try:
            # Directory bundle (extracted .agrc or development mode)
            if path.is_dir():
                flow_file = path / "flow.json"
                if flow_file.exists():
                    with open(flow_file, encoding="utf-8") as f:
                        data = json.load(f)
                    return self.load_dict(data)
                else:
                    raise LoaderError(f"No flow.json found in directory: {path}")

            if path.suffix == ".json":
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                return self.load_dict(data)

            # .agrc ZIP file - should be extracted before loading
            if path.suffix == ".agrc":
                raise LoaderError(f".agrc files must be extracted first. Use CLI to run: agenarc run {path}")

            raise LoaderError(f"Unsupported file type: {path.suffix}")
        finally:
            self._parent_path = None

    def load_dict(self, data: dict[str, Any]) -> Graph:
        """
        Load protocol from a dictionary.

        Args:
            data: Protocol dictionary

        Returns:
            Graph object
        """
        if self.validate:
            self._validate_schema(data)

        return self._parse_graph(data)

    def _validate_schema(self, data: dict[str, Any]) -> None:
        """
        Validate data against JSON schema.

        Args:
            data: Protocol data to validate

        Raises:
            SchemaValidationError: If validation fails
        """
        try:
            import jsonschema

            jsonschema.validate(instance=data, schema=AGENARC_SCHEMA)
        except ImportError:
            global _jsonschema_available
            if _jsonschema_available is None:
                _jsonschema_available = False
                logger.warning(
                    "jsonschema not installed. Protocol validation skipped. Install with: pip install jsonschema"
                )
        except jsonschema.ValidationError as e:
            raise SchemaValidationError(f"Schema validation failed: {e.message}") from e

    def _parse_graph(self, data: dict[str, Any]) -> Graph:
        """
        Parse dictionary into Graph object.

        Args:
            data: Protocol dictionary

        Returns:
            Graph object
        """
        nodes = [self._parse_node(n) for n in data.get("nodes", [])]
        edges = [self._parse_edge(e) for e in data.get("edges", [])]

        # Expand output_to_context shorthand into Context_Set nodes
        nodes, edges = self._expand_output_to_context(nodes, edges)

        return Graph(
            version=data.get("version", "1.0.0"),
            nodes=nodes,
            edges=edges,
        )

    def _expand_output_to_context(self, nodes: list[Node], edges: list[Edge]) -> tuple[list[Node], list[Edge]]:
        """
        Expand output_to_context shorthand in node configs into Context_Set nodes.

        When a node has output_to_context in its config like:
            "output_to_context": {"result": {"ref": "outputs.response"}}

        This is expanded into a Context_Set node that runs after the original node.

        Args:
            nodes: List of parsed nodes
            edges: List of parsed edges

        Returns:
            Tuple of (expanded_nodes, expanded_edges)
        """
        expanded_nodes = list(nodes)
        expanded_edges = list(edges)
        exist_ids = {n.id for n in nodes}

        for node in nodes:
            config = node.metadata.get("config", {})
            output_to_context = config.get("output_to_context", {})

            if not output_to_context:
                continue

            # Validate output ports exist on source node
            source_output_names = {p.name for p in node.outputs}

            # Create a Context_Set node for each output_to_context entry
            for ctx_key, mapping in output_to_context.items():
                ref = mapping.get("ref", "")

                # Parse the ref to get source node and output port
                # Expected format: "outputs.<port_name>"
                if not ref.startswith("outputs."):
                    continue

                output_port = ref[len("outputs.") :]

                # Validate output port exists
                if source_output_names and output_port not in source_output_names:
                    import warnings

                    warnings.warn(
                        f"output_to_context references port '{output_port}' "
                        f"on node '{node.id}' but node has outputs: {source_output_names}",
                        stacklevel=2,
                    )

                # Generate unique ID for the Context_Set node
                context_node_id = f"{node.id}_ctx_{ctx_key}"

                # Check for collision with existing node IDs
                if context_node_id in exist_ids:
                    import warnings

                    warnings.warn(
                        f"Generated Context_Set node ID '{context_node_id}' collides with existing node ID. Skipping.",
                        stacklevel=2,
                    )
                    continue

                # Create the Context_Set node
                # Store the context key name in config so Context_Set operator can read it
                context_node = Node(
                    id=context_node_id,
                    type=NodeType.CONTEXT_SET,
                    label=f"Set {ctx_key}",
                    config=NodeConfig(data={"_context_key": ctx_key}),
                )

                # Create edge from original node's output to context node's value input
                context_edge = Edge(
                    source=node.id,
                    sourcePort=output_port,
                    target=context_node_id,
                    targetPort="value",
                )
                expanded_nodes.append(context_node)
                expanded_edges.append(context_edge)
                exist_ids.add(context_node_id)

        return expanded_nodes, expanded_edges

    def _parse_node(self, data: dict[str, Any]) -> Node:
        """
        Parse node dictionary into Node object.

        Args:
            data: Node dictionary

        Returns:
            Node object
        """
        node_type = self._node_types.get(data.get("type", ""))
        if not node_type:
            raise LoaderError(f"Unknown node type: {data.get('type')}")

        inputs = [self._parse_port(p) for p in data.get("inputs", [])]
        outputs = [self._parse_port(p) for p in data.get("outputs", [])]

        config = NodeConfig(data=data.get("config", {}))

        # Auto-resolve ports from SubGraph node
        if node_type == NodeType.SUBGRAPH and "bundle" in config.data:
            child_ports = self._resolve_subgraph_ports(config.data["bundle"])
            if child_ports is not None:
                inputs = child_ports["inputs"]
                outputs = child_ports["outputs"]

        # For Router nodes, convert conditions from dicts to Condition objects
        if node_type == NodeType.ROUTER and "conditions" in config.data:
            raw_conditions = config.data["conditions"]
            parsed_conditions = [self._parse_condition(c) for c in raw_conditions]
            config.data["conditions"] = parsed_conditions

        error_handling = None
        if "errorHandling" in data:
            eh_data = data["errorHandling"]
            error_handling = ErrorHandling(
                strategy=self._error_strategies.get(eh_data.get("strategy", "abort"), ErrorStrategy.ABORT),
                maxRetries=eh_data.get("maxRetries", 0),
                errorPort=eh_data.get("errorPort", "error"),
                fallbackNode=eh_data.get("fallbackNode"),
            )

        return Node(
            id=data["id"],
            type=node_type,
            label=data.get("label", data["id"]),
            description=data.get("description", ""),
            inputs=inputs,
            outputs=outputs,
            config=config,
            errorHandling=error_handling,
            checkpoint=data.get("checkpoint", False),
            idempotent=data.get("idempotent", True),
            metadata=data,
        )

    def _parse_port(self, data: dict[str, Any]) -> Port:
        """
        Parse port dictionary into Port object.

        Args:
            data: Port dictionary

        Returns:
            Port object
        """
        return Port(
            name=data["name"],
            type=data.get("type", "any"),
            description=data.get("description", ""),
            default=data.get("default"),
        )

    def _parse_edge(self, data: dict[str, Any]) -> Edge:
        """
        Parse edge dictionary into Edge object.

        Args:
            data: Edge dictionary

        Returns:
            Edge object
        """
        return Edge(
            source=data["source"],
            sourcePort=data.get("sourcePort", ""),
            target=data["target"],
            targetPort=data.get("targetPort", ""),
            label=data.get("label", ""),
            style=data.get("style", "solid"),
        )

    def _parse_condition(self, data: dict[str, Any]) -> Condition:
        """
        Parse condition dictionary into Condition object.

        Args:
            data: Condition dictionary

        Returns:
            Condition object
        """
        and_conditions = None
        or_conditions = None
        not_condition = None

        if "and" in data:
            and_conditions = [self._parse_condition(c) for c in data["and"]]
        if "or" in data:
            or_conditions = [self._parse_condition(c) for c in data["or"]]
        if "not" in data:
            not_condition = self._parse_condition(data["not"])

        return Condition(
            ref=data.get("ref"),
            operator=self._condition_operators.get(data.get("operator", "").lower()),
            value=data.get("value"),
            output=data.get("output"),
            and_conditions=and_conditions,
            or_conditions=or_conditions,
            not_condition=not_condition,
        )

    def _get_node_output_ports(self, node: Node) -> list[Port]:
        """Get output ports for a node, resolving from operator if possible."""
        # If node has ports set by loader, use them
        if node.outputs:
            return node.outputs
        # Otherwise, try to get ports from built-in operator
        try:
            from agenarc.operators.builtin import BUILTIN_OPERATORS
            op_class = BUILTIN_OPERATORS.get(node.type.value)
            if op_class is not None:
                op = op_class()
                return op.get_output_ports()
        except (ImportError, Exception):
            pass
        return node.outputs

    def _get_node_input_ports(self, node: Node) -> list[Port]:
        """Get input ports for a node, resolving from operator if possible."""
        if node.inputs:
            return node.inputs
        try:
            from agenarc.operators.builtin import BUILTIN_OPERATORS
            op_class = BUILTIN_OPERATORS.get(node.type.value)
            if op_class is not None:
                op = op_class()
                return op.get_input_ports()
        except (ImportError, Exception):
            pass
        return node.inputs

    def _resolve_subgraph_ports(self, bundle_ref: str) -> dict | None:
        """
        Resolve SubGraph input/output ports from child bundle.

        Input ports = trigger node output ports from child bundle.
        Output ports = terminal node output ports from child bundle.

        Args:
            bundle_ref: Bundle reference string from node config

        Returns:
            Dict with "inputs" and "outputs" lists, or None if parent path unknown
        """
        if not self._parent_path:
            return None

        # Resolve child bundle path
        try:
            child_path = self._resolve_bundle_ref(bundle_ref, self._parent_path)
        except LoaderError:
            # Bundle not found — skip port resolution, operator will fail at runtime
            return None

        resolved_str = str(child_path.resolve())

        # Check for recursive references
        if resolved_str in self._resolving_stack:
            raise LoaderError(f"Recursive SubGraph reference detected: {bundle_ref}")

        self._resolving_stack.append(resolved_str)
        try:
            child_loader = ProtocolLoader(validate=self.validate)
            child_loader._resolving_stack = self._resolving_stack
            try:
                child_graph = child_loader.load(child_path)
            except LoaderError:
                # Child bundle failed to load — skip port resolution
                return None
        finally:
            self._resolving_stack.pop()

        # Find trigger outputs → SubGraph input ports
        input_ports: list[Port] = []
        for node in child_graph.nodes:
            if node.type == NodeType.TRIGGER:
                for port in self._get_node_output_ports(node):
                    input_ports.append(
                        Port(
                            name=port.name,
                            type=port.type,
                            description=f"From child trigger '{node.id}': {port.description}",
                        )
                    )

        # Find terminal nodes (no outgoing edges at all) → SubGraph output ports
        terminal_nodes: list[Node] = []
        for node in child_graph.nodes:
            outgoing = child_graph.get_outgoing_edges(node.id)
            if not outgoing:
                terminal_nodes.append(node)

        # Count port name occurrences for collision detection
        port_name_counts: dict[str, int] = {}
        for node in terminal_nodes:
            for port in self._get_node_output_ports(node):
                port_name_counts[port.name] = port_name_counts.get(port.name, 0) + 1

        # Build output ports with collision handling
        output_ports: list[Port] = []
        for node in terminal_nodes:
            for port in self._get_node_output_ports(node):
                if port_name_counts.get(port.name, 0) > 1:
                    output_ports.append(
                        Port(
                            name=f"{node.id}.{port.name}",
                            type=port.type,
                            description=f"From terminal node '{node.id}': {port.description}",
                        )
                    )
                else:
                    output_ports.append(
                        Port(
                            name=port.name,
                            type=port.type,
                            description=f"From terminal node '{node.id}': {port.description}",
                        )
                    )

        return {"inputs": input_ports, "outputs": output_ports}

    @staticmethod
    def _resolve_bundle_ref(bundle_ref: str, parent_path: Path) -> Path:
        """
        Resolve a SubGraph bundle reference to an absolute path.

        Resolution order:
        1. Relative to parent path
        2. As absolute path

        Args:
            bundle_ref: Bundle reference (relative or absolute path)
            parent_path: Path of the parent bundle

        Returns:
            Resolved absolute Path

        Raises:
            LoaderError: If bundle cannot be found
        """
        # If absolute path, use it directly
        if Path(bundle_ref).is_absolute():
            child_path = Path(bundle_ref)
            if child_path.exists():
                return child_path
            raise LoaderError(f"SubGraph bundle not found (absolute): {bundle_ref}")

        # Check relative to parent path
        child_path = parent_path / bundle_ref if parent_path.is_dir() else parent_path.parent / bundle_ref

        if child_path.exists():
            return child_path

        # Try sub/ directory (for embedded bundles)
        if parent_path.is_dir():
            sub_child_path = parent_path / "sub" / bundle_ref
        else:
            sub_child_path = parent_path.parent / "sub" / bundle_ref
        if sub_child_path.exists():
            return sub_child_path

        # Try current working directory as fallback
        cwd_path = Path.cwd() / bundle_ref
        if cwd_path.exists():
            return cwd_path

        checked = f"{child_path}, {sub_child_path}, {cwd_path}"
        raise LoaderError(f"SubGraph bundle not found: {bundle_ref} (checked: {checked})")


def load(path: str | Path) -> Graph:
    """
    Convenience function to load a protocol file.

    Args:
        path: Path to flow.json

    Returns:
        Graph object
    """
    loader = ProtocolLoader()
    return loader.load(path)
