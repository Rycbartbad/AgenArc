"""
AgenArc Protocol Schema

Defines JSON Schema for directed-graph Agent orchestration protocol.
Based on ARCHITECTURE.md DSL specification.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeType(str, Enum):
    """Node type enumeration."""
    TRIGGER = "Trigger"
    LLM_TASK = "LLM_Task"
    ROUTER = "Router"
    LOOP_CONTROL = "Loop_Control"
    MEMORY_IO = "Memory_I/O"
    SCRIPT_NODE = "Script_Node"
    SUBGRAPH = "Subgraph"
    LOG = "Log"
    CONTEXT_SET = "Context_Set"
    CONTEXT_GET = "Context_Get"


class ErrorStrategy(str, Enum):
    """Error handling strategies."""
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ABORT = "abort"


class TriggerSource(str, Enum):
    """Trigger source types."""
    MANUAL = "manual"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    EVENT = "event"


class MemoryMode(str, Enum):
    """Memory I/O modes."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"


class ConditionOperator(str, Enum):
    """Condition operators."""
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    STARTS_WITH = "startsWith"
    ENDS_WITH = "endsWith"
    IN = "in"
    NOT_IN = "notIn"
    EXISTS = "exists"
    NOT_EXISTS = "notExists"


@dataclass
class Port:
    """Input or output port definition."""
    name: str
    type: str  # "any", "string", "number", "boolean", "object", "array"
    description: str = ""
    default: Any = None


@dataclass
class ErrorHandling:
    """Node error handling configuration."""
    strategy: ErrorStrategy = ErrorStrategy.ABORT
    maxRetries: int = 0
    errorPort: str = "error"
    fallbackNode: Optional[str] = None


@dataclass
class Condition:
    """Condition expression for Router and Loop_Control."""
    ref: Optional[str] = None
    operator: Optional[ConditionOperator] = None
    value: Any = None
    output: Optional[str] = None
    # Combinators
    and_conditions: Optional[List["Condition"]] = None
    or_conditions: Optional[List["Condition"]] = None
    not_condition: Optional["Condition"] = None


@dataclass
class NodeConfig:
    """Node-specific configuration storage."""
    data: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value


@dataclass
class Node:
    """
    Base node structure for the directed graph.

    Represents an atomic unit of work in the Agent flow.
    """
    id: str
    type: NodeType
    label: str
    description: str = ""

    # Ports
    inputs: List[Port] = field(default_factory=list)
    outputs: List[Port] = field(default_factory=list)

    # Configuration
    config: NodeConfig = field(default_factory=NodeConfig)

    # Error handling
    errorHandling: Optional[ErrorHandling] = None

    # Checkpoint settings
    checkpoint: bool = False
    idempotent: bool = True

    # Node-type specific data
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """
    Edge structure representing control flow connection.

    Edges only carry control-flow semantics (execution order).
    Data is passed through global Context.
    """
    source: str
    target: str
    sourcePort: str = ""
    targetPort: str = ""

    # Metadata (for IDE rendering only)
    label: str = ""
    style: str = "solid"  # "solid" or "dashed"


@dataclass
class GraphMetadata:
    """Metadata for the graph."""
    name: str = ""
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    created: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class Graph:
    """
    Complete directed graph structure.

    This is the root structure loaded from flow.json.
    """
    version: str = "1.0.0"
    metadata: GraphMetadata = field(default_factory=GraphMetadata)
    entryPoint: str = ""
    errorNode: str = ""  # Global error handler node ID

    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_outgoing_edges(self, node_id: str) -> List[Edge]:
        """Get all edges originating from a node."""
        return [e for e in self.edges if e.source == node_id]

    def get_incoming_edges(self, node_id: str) -> List[Edge]:
        """Get all edges targeting a node."""
        return [e for e in self.edges if e.target == node_id]


# JSON Schema for validation (compatible with jsonschema library)
AGENARC_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "AgenArc Protocol",
    "description": "Directed-graph agent orchestration protocol",
    "type": "object",
    "required": ["version", "entryPoint", "nodes", "edges"],
    "properties": {
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
            "description": "Semantic version"
        },
        "metadata": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "author": {"type": "string"},
                "version": {"type": "string"},
                "created": {"type": "string", "format": "date-time"},
                "tags": {"type": "array", "items": {"type": "string"}}
            }
        },
        "entryPoint": {
            "type": "string",
            "description": "ID of the entry Trigger node"
        },
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "type", "label"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [t.value for t in NodeType]
                    },
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                    "inputs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "type"],
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "description": {"type": "string"},
                                "default": {}
                            }
                        }
                    },
                    "outputs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "type"],
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "description": {"type": "string"},
                                "default": {}
                            }
                        }
                    },
                    "config": {"type": "object"},
                    "errorHandling": {
                        "type": "object",
                        "properties": {
                            "strategy": {
                                "type": "string",
                                "enum": [s.value for s in ErrorStrategy]
                            },
                            "maxRetries": {"type": "integer"},
                            "errorPort": {"type": "string"},
                            "fallbackNode": {"type": "string"}
                        }
                    },
                    "checkpoint": {"type": "boolean"},
                    "idempotent": {"type": "boolean"}
                }
            }
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "target"],
                "properties": {
                    "source": {"type": "string"},
                    "sourcePort": {"type": "string"},
                    "target": {"type": "string"},
                    "targetPort": {"type": "string"},
                    "label": {"type": "string"},
                    "style": {"type": "string", "enum": ["solid", "dashed"]}
                }
            }
        }
    }
}
