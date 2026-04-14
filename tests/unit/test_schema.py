"""Unit tests for protocol/schema.py."""

import pytest
from agenarc.protocol.schema import (
    NodeType,
    Edge,
    Graph,
    Node,
    Port,
    ErrorHandling,
    ErrorStrategy,
    GraphMetadata,
    NodeConfig,
    Condition,
    ConditionOperator,
    TriggerSource,
    MemoryMode,
)


class TestPort:
    """Tests for Port dataclass."""

    def test_port_creation(self):
        """Test Port creation with all fields."""
        port = Port(name="test", type="string", description="Test port", default="value")
        assert port.name == "test"
        assert port.type == "string"
        assert port.description == "Test port"
        assert port.default == "value"

    def test_port_optional_fields(self):
        """Test Port creation with optional fields omitted."""
        port = Port(name="test", type="any")
        assert port.description == ""
        assert port.default is None


class TestErrorHandling:
    """Tests for ErrorHandling dataclass."""

    def test_error_handling_defaults(self):
        """Test ErrorHandling with defaults."""
        eh = ErrorHandling()
        assert eh.strategy == ErrorStrategy.ABORT
        assert eh.maxRetries == 0
        assert eh.errorPort == "error"
        assert eh.fallbackNode is None

    def test_error_handling_custom(self):
        """Test ErrorHandling with custom values."""
        eh = ErrorHandling(
            strategy=ErrorStrategy.RETRY,
            maxRetries=3,
            errorPort="custom_error",
            fallbackNode="fallback_node"
        )
        assert eh.strategy == ErrorStrategy.RETRY
        assert eh.maxRetries == 3
        assert eh.errorPort == "custom_error"
        assert eh.fallbackNode == "fallback_node"


class TestNodeConfig:
    """Tests for NodeConfig dataclass."""

    def test_node_config_empty(self):
        """Test NodeConfig creation with empty dict."""
        config = NodeConfig()
        assert config.data == {}
        assert config.get("key") is None
        assert config.get("key", "default") == "default"

    def test_node_config_with_data(self):
        """Test NodeConfig creation with data."""
        config = NodeConfig(data={"key": "value", "num": 42})
        assert config.get("key") == "value"
        assert config.get("num") == 42

    def test_node_config_set(self):
        """Test setting values in NodeConfig."""
        config = NodeConfig()
        config.set("new_key", "new_value")
        assert config.get("new_key") == "new_value"

    def test_node_config_item_access(self):
        """Test dict-like item access."""
        config = NodeConfig(data={"a": 1, "b": 2})
        assert config["a"] == 1
        config["c"] = 3
        assert config["c"] == 3


class TestNode:
    """Tests for Node dataclass."""

    def test_node_creation(self):
        """Test Node creation with required fields."""
        node = Node(id="test_node", type=NodeType.TRIGGER, label="Test Node")
        assert node.id == "test_node"
        assert node.type == NodeType.TRIGGER
        assert node.label == "Test Node"

    def test_node_with_ports(self):
        """Test Node with input/output ports."""
        inputs = [Port(name="input1", type="string")]
        outputs = [Port(name="output1", type="any")]
        node = Node(
            id="test_node",
            type=NodeType.LLM_TASK,
            label="Test",
            inputs=inputs,
            outputs=outputs
        )
        assert len(node.inputs) == 1
        assert len(node.outputs) == 1

    def test_node_with_error_handling(self):
        """Test Node with error handling."""
        eh = ErrorHandling(strategy=ErrorStrategy.FALLBACK, fallbackNode="fb")
        node = Node(
            id="test_node",
            type=NodeType.LLM_TASK,
            label="Test",
            errorHandling=eh
        )
        assert node.errorHandling.strategy == ErrorStrategy.FALLBACK
        assert node.errorHandling.fallbackNode == "fb"

    def test_node_checkpoint_settings(self):
        """Test Node checkpoint settings."""
        node = Node(
            id="test_node",
            type=NodeType.MEMORY_IO,
            label="Test",
            checkpoint=True,
            idempotent=False
        )
        assert node.checkpoint is True
        assert node.idempotent is False


class TestEdge:
    """Tests for Edge dataclass."""

    def test_edge_creation(self):
        """Test Edge creation with required fields."""
        edge = Edge(source="node_a", target="node_b")
        assert edge.source == "node_a"
        assert edge.target == "node_b"
        assert edge.sourcePort == ""
        assert edge.targetPort == ""

    def test_edge_with_ports(self):
        """Test Edge creation with port specifications."""
        edge = Edge(
            source="node_a",
            sourcePort="out1",
            target="node_b",
            targetPort="in1",
            label="connection",
            style="dashed"
        )
        assert edge.sourcePort == "out1"
        assert edge.targetPort == "in1"
        assert edge.label == "connection"
        assert edge.style == "dashed"

    def test_edge_default_style(self):
        """Test Edge default style is solid."""
        edge = Edge(source="a", target="b")
        assert edge.style == "solid"


class TestGraphMetadata:
    """Tests for GraphMetadata dataclass."""

    def test_graph_metadata_defaults(self):
        """Test GraphMetadata with defaults."""
        meta = GraphMetadata()
        assert meta.name == ""
        assert meta.description == ""
        assert meta.author == ""
        assert meta.version == "1.0.0"
        assert meta.created == ""
        assert meta.tags == []

    def test_graph_metadata_full(self):
        """Test GraphMetadata with all fields."""
        meta = GraphMetadata(
            name="Test Graph",
            description="A test graph",
            author="Tester",
            version="2.0.0",
            created="2026-01-01T00:00:00",
            tags=["test", "example"]
        )
        assert meta.name == "Test Graph"
        assert len(meta.tags) == 2


class TestGraph:
    """Tests for Graph dataclass."""

    def test_graph_creation(self):
        """Test Graph creation."""
        graph = Graph(
            version="1.0.0",
            nodes=[],
            edges=[]
        )
        assert graph.version == "1.0.0"
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_graph_get_node(self):
        """Test getting node by ID."""
        nodes = [
            Node(id="node1", type=NodeType.TRIGGER, label="Node 1"),
            Node(id="node2", type=NodeType.LLM_TASK, label="Node 2"),
        ]
        graph = Graph(version="1.0.0", nodes=nodes, edges=[])

        found = graph.get_node("node1")
        assert found is not None
        assert found.id == "node1"

        not_found = graph.get_node("nonexistent")
        assert not_found is None

    def test_graph_get_outgoing_edges(self):
        """Test getting outgoing edges."""
        nodes = [
            Node(id="a", type=NodeType.TRIGGER, label="A"),
            Node(id="b", type=NodeType.LLM_TASK, label="B"),
        ]
        edges = [
            Edge(source="a", target="b"),
            Edge(source="b", target="c"),
        ]
        graph = Graph(version="1.0.0", nodes=nodes, edges=edges)

        outgoing = graph.get_outgoing_edges("a")
        assert len(outgoing) == 1
        assert outgoing[0].target == "b"

        outgoing_b = graph.get_outgoing_edges("b")
        assert len(outgoing_b) == 1
        assert outgoing_b[0].target == "c"

    def test_graph_get_incoming_edges(self):
        """Test getting incoming edges."""
        nodes = [
            Node(id="a", type=NodeType.TRIGGER, label="A"),
            Node(id="b", type=NodeType.LLM_TASK, label="B"),
        ]
        edges = [
            Edge(source="a", target="b"),
            Edge(source="a", target="b"),
        ]
        graph = Graph(version="1.0.0", nodes=nodes, edges=edges)

        incoming = graph.get_incoming_edges("b")
        assert len(incoming) == 2


class TestEnums:
    """Tests for enum types."""

    def test_node_type_values(self):
        """Test NodeType enum values."""
        assert NodeType.TRIGGER.value == "Trigger"
        assert NodeType.LLM_TASK.value == "LLM_Task"
        assert NodeType.ROUTER.value == "Router"
        assert NodeType.MEMORY_IO.value == "Memory_I/O"
        assert NodeType.SCRIPT_NODE.value == "Script_Node"
        assert NodeType.SUBGRAPH.value == "Subgraph"
        assert NodeType.LOG.value == "Log"

    def test_error_strategy_values(self):
        """Test ErrorStrategy enum values."""
        assert ErrorStrategy.RETRY.value == "retry"
        assert ErrorStrategy.FALLBACK.value == "fallback"
        assert ErrorStrategy.SKIP.value == "skip"
        assert ErrorStrategy.ABORT.value == "abort"

    def test_condition_operator_values(self):
        """Test ConditionOperator enum values."""
        assert ConditionOperator.EQ.value == "eq"
        assert ConditionOperator.NE.value == "ne"
        assert ConditionOperator.GT.value == "gt"
        assert ConditionOperator.CONTAINS.value == "contains"
        assert ConditionOperator.EXISTS.value == "exists"

    def test_trigger_source_values(self):
        """Test TriggerSource enum values."""
        assert TriggerSource.MANUAL.value == "manual"
        assert TriggerSource.WEBHOOK.value == "webhook"
        assert TriggerSource.SCHEDULE.value == "schedule"
        assert TriggerSource.EVENT.value == "event"

    def test_memory_mode_values(self):
        """Test MemoryMode enum values."""
        assert MemoryMode.READ.value == "read"
        assert MemoryMode.WRITE.value == "write"
        assert MemoryMode.DELETE.value == "delete"
