"""
Protocol Loader

Loads and parses AgenArc protocol JSON files into Graph objects.
Supports both standalone flow.json and .arc bundle format.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agenarc.protocol.schema import (
    AGENARC_SCHEMA,
    Condition,
    Edge,
    ErrorHandling,
    ErrorStrategy,
    Graph,
    GraphMetadata,
    Node,
    NodeConfig,
    NodeType,
    Port,
    TriggerSource,
    MemoryMode,
    ConditionOperator,
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

    def load(self, source: Union[str, Path, Dict[str, Any]]) -> Graph:
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

    def load_file(self, path: Union[str, Path]) -> Graph:
        """
        Load protocol from a JSON file.

        Args:
            path: Path to flow.json or protocol dict

        Returns:
            Graph object
        """
        path = Path(path)

        if not path.exists():
            raise LoaderError(f"File not found: {path}")

        if path.suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            raise LoaderError(f"Unsupported file type: {path.suffix}")

        return self.load_dict(data)

    def load_dict(self, data: Dict[str, Any]) -> Graph:
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

    def _validate_schema(self, data: Dict[str, Any]) -> None:
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
            # jsonschema not installed, skip validation
            pass
        except jsonschema.ValidationError as e:
            raise SchemaValidationError(f"Schema validation failed: {e.message}")

    def _parse_graph(self, data: Dict[str, Any]) -> Graph:
        """
        Parse dictionary into Graph object.

        Args:
            data: Protocol dictionary

        Returns:
            Graph object
        """
        metadata_data = data.get("metadata", {})
        metadata = GraphMetadata(
            name=metadata_data.get("name", ""),
            description=metadata_data.get("description", ""),
            author=metadata_data.get("author", ""),
            version=metadata_data.get("version", "1.0.0"),
            created=metadata_data.get("created", datetime.now().isoformat()),
            tags=metadata_data.get("tags", []),
        )

        nodes = [self._parse_node(n) for n in data.get("nodes", [])]
        edges = [self._parse_edge(e) for e in data.get("edges", [])]

        return Graph(
            version=data.get("version", "1.0.0"),
            metadata=metadata,
            entryPoint=data.get("entryPoint", ""),
            nodes=nodes,
            edges=edges,
        )

    def _parse_node(self, data: Dict[str, Any]) -> Node:
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

        error_handling = None
        if "errorHandling" in data:
            eh_data = data["errorHandling"]
            error_handling = ErrorHandling(
                strategy=self._error_strategies.get(
                    eh_data.get("strategy", "abort"), ErrorStrategy.ABORT
                ),
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

    def _parse_port(self, data: Dict[str, Any]) -> Port:
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

    def _parse_edge(self, data: Dict[str, Any]) -> Edge:
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

    def _parse_condition(self, data: Dict[str, Any]) -> Condition:
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
            operator=self._condition_operators.get(data.get("operator")),
            value=data.get("value"),
            output=data.get("output"),
            and_conditions=and_conditions,
            or_conditions=or_conditions,
            not_condition=not_condition,
        )


def load(path: Union[str, Path]) -> Graph:
    """
    Convenience function to load a protocol file.

    Args:
        path: Path to flow.json

    Returns:
        Graph object
    """
    loader = ProtocolLoader()
    return loader.load(path)
