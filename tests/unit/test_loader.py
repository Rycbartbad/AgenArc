"""Unit tests for protocol/loader.py."""

import json
import pytest
from pathlib import Path
from agenarc.protocol.loader import ProtocolLoader, LoaderError, SchemaValidationError
from agenarc.protocol.schema import NodeType, Edge, Graph, Node, Port


class TestProtocolLoader:
    """Tests for ProtocolLoader class."""

    def test_loader_creation(self):
        """Test loader creation."""
        loader = ProtocolLoader()
        assert loader.validate is True

    def test_loader_no_validation(self):
        """Test loader without validation."""
        loader = ProtocolLoader(validate=False)
        assert loader.validate is False

    def test_load_from_dict(self):
        """Test loading from dictionary."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                }
            ],
            "edges": []
        }
        loader = ProtocolLoader(validate=False)
        graph = loader.load_dict(data)

        assert graph.version == "1.0.0"
        assert graph.entryPoint == "trigger_1"
        assert len(graph.nodes) == 1

    def test_load_from_dict_with_metadata(self):
        """Test loading from dict with metadata."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "metadata": {
                "name": "Test Graph",
                "author": "Tester"
            },
            "nodes": [],
            "edges": []
        }
        loader = ProtocolLoader(validate=False)
        graph = loader.load_dict(data)

        assert graph.metadata.name == "Test Graph"
        assert graph.metadata.author == "Tester"

    def test_load_node_with_ports(self):
        """Test loading node with input/output ports."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {
                    "id": "llm_task",
                    "type": "LLM_Task",
                    "label": "LLM",
                    "inputs": [
                        {"name": "prompt", "type": "string"}
                    ],
                    "outputs": [
                        {"name": "response", "type": "string"}
                    ]
                }
            ],
            "edges": []
        }
        loader = ProtocolLoader(validate=False)
        graph = loader.load_dict(data)

        node = graph.get_node("llm_task")
        assert len(node.inputs) == 1
        assert len(node.outputs) == 1
        assert node.inputs[0].name == "prompt"
        assert node.outputs[0].name == "response"

    def test_load_node_with_error_handling(self):
        """Test loading node with error handling."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {
                    "id": "risky_node",
                    "type": "LLM_Task",
                    "label": "Risky",
                    "errorHandling": {
                        "strategy": "fallback",
                        "maxRetries": 3,
                        "errorPort": "error",
                        "fallbackNode": "fallback"
                    }
                }
            ],
            "edges": []
        }
        loader = ProtocolLoader(validate=False)
        graph = loader.load_dict(data)

        node = graph.get_node("risky_node")
        assert node.errorHandling is not None
        assert node.errorHandling.strategy.value == "fallback"
        assert node.errorHandling.maxRetries == 3
        assert node.errorHandling.fallbackNode == "fallback"

    def test_load_node_with_config(self):
        """Test loading node with config."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {
                    "id": "config_node",
                    "type": "LLM_Task",
                    "label": "Config",
                    "config": {
                        "model": "gpt-4",
                        "temperature": 0.5
                    }
                }
            ],
            "edges": []
        }
        loader = ProtocolLoader(validate=False)
        graph = loader.load_dict(data)

        node = graph.get_node("config_node")
        assert node.config.get("model") == "gpt-4"
        assert node.config.get("temperature") == 0.5

    def test_load_edges(self):
        """Test loading edges."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "a", "type": "Trigger", "label": "A"},
                {"id": "b", "type": "Trigger", "label": "B"},
            ],
            "edges": [
                {
                    "source": "a",
                    "sourcePort": "out",
                    "target": "b",
                    "targetPort": "in",
                    "label": "flow",
                    "style": "dashed"
                }
            ]
        }
        loader = ProtocolLoader(validate=False)
        graph = loader.load_dict(data)

        assert len(graph.edges) == 1
        edge = graph.edges[0]
        assert edge.source == "a"
        assert edge.sourcePort == "out"
        assert edge.target == "b"
        assert edge.targetPort == "in"
        assert edge.label == "flow"
        assert edge.style == "dashed"

    def test_load_unknown_node_type(self):
        """Test loading with unknown node type raises error."""
        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {
                    "id": "unknown",
                    "type": "UnknownType",
                    "label": "Unknown"
                }
            ],
            "edges": []
        }
        loader = ProtocolLoader(validate=False)
        with pytest.raises(LoaderError, match="Unknown node type"):
            loader.load_dict(data)

    def test_load_invalid_source_type(self):
        """Test loading from invalid source type raises error."""
        loader = ProtocolLoader()
        with pytest.raises(LoaderError, match="Unsupported source type"):
            loader.load([1, 2, 3])  # type: ignore

    def test_load_nonexistent_file(self):
        """Test loading nonexistent file raises error."""
        loader = ProtocolLoader()
        with pytest.raises(LoaderError, match="File not found"):
            loader.load_file("nonexistent.json")

    def test_load_unsupported_file_type(self):
        """Test loading unsupported file type raises error."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            f.flush()
            loader = ProtocolLoader()
            with pytest.raises(LoaderError, match="Unsupported file type"):
                loader.load_file(f.name)


class TestLoadFunction:
    """Tests for load() convenience function."""

    def test_load_function(self):
        """Test load() convenience function."""
        from agenarc.protocol.loader import load

        data = {
            "version": "1.0.0",
            "entryPoint": "trigger_1",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"}
            ],
            "edges": []
        }

        # Load from dict works
        graph = load(data)
        assert graph.version == "1.0.0"


class TestParseEdge:
    """Tests for edge parsing."""

    def test_parse_edge_minimal(self):
        """Test parsing edge with minimal fields."""
        loader = ProtocolLoader()
        edge = loader._parse_edge({"source": "a", "target": "b"})

        assert edge.source == "a"
        assert edge.target == "b"
        assert edge.sourcePort == ""
        assert edge.targetPort == ""
        assert edge.style == "solid"

    def test_parse_edge_full(self):
        """Test parsing edge with all fields."""
        edge_data = {
            "source": "a",
            "sourcePort": "out",
            "target": "b",
            "targetPort": "in",
            "label": "connection",
            "style": "dashed"
        }
        loader = ProtocolLoader()
        edge = loader._parse_edge(edge_data)

        assert edge.source == "a"
        assert edge.sourcePort == "out"
        assert edge.target == "b"
        assert edge.targetPort == "in"
        assert edge.label == "connection"
        assert edge.style == "dashed"


class TestParsePort:
    """Tests for port parsing."""

    def test_parse_port_minimal(self):
        """Test parsing port with minimal fields."""
        loader = ProtocolLoader()
        port = loader._parse_port({"name": "test", "type": "string"})

        assert port.name == "test"
        assert port.type == "string"
        assert port.description == ""
        assert port.default is None

    def test_parse_port_full(self):
        """Test parsing port with all fields."""
        port_data = {
            "name": "test",
            "type": "number",
            "description": "Test port",
            "default": 42
        }
        loader = ProtocolLoader()
        port = loader._parse_port(port_data)

        assert port.name == "test"
        assert port.type == "number"
        assert port.description == "Test port"
        assert port.default == 42
