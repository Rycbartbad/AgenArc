"""Unit tests for graph/traversal.py."""

import pytest
from agenarc.protocol.schema import Graph, Node, Edge, NodeType
from agenarc.graph.traversal import GraphTraversal, CycleError


class TestGraphTraversal:
    """Tests for GraphTraversal class."""

    def create_linear_graph(self):
        """Create a simple linear graph: a -> b -> c"""
        nodes = [
            Node(id="a", type=NodeType.TRIGGER, label="A"),
            Node(id="b", type=NodeType.LLM_TASK, label="B"),
            Node(id="c", type=NodeType.LLM_TASK, label="C"),
        ]
        edges = [
            Edge(source="a", target="b"),
            Edge(source="b", target="c"),
        ]
        return Graph(version="1.0.0", nodes=nodes, edges=edges)

    def create_branching_graph(self):
        """Create a branching graph: a -> b, a -> c"""
        nodes = [
            Node(id="a", type=NodeType.TRIGGER, label="A"),
            Node(id="b", type=NodeType.LLM_TASK, label="B"),
            Node(id="c", type=NodeType.LLM_TASK, label="C"),
        ]
        edges = [
            Edge(source="a", target="b"),
            Edge(source="a", target="c"),
        ]
        return Graph(version="1.0.0", nodes=nodes, edges=edges)

    def create_diamond_graph(self):
        """Create a diamond graph: a -> b, a -> c, b -> d, c -> d"""
        nodes = [
            Node(id="a", type=NodeType.TRIGGER, label="A"),
            Node(id="b", type=NodeType.LLM_TASK, label="B"),
            Node(id="c", type=NodeType.LLM_TASK, label="C"),
            Node(id="d", type=NodeType.LLM_TASK, label="D"),
        ]
        edges = [
            Edge(source="a", target="b"),
            Edge(source="a", target="c"),
            Edge(source="b", target="d"),
            Edge(source="c", target="d"),
        ]
        return Graph(version="1.0.0", nodes=nodes, edges=edges)

    def test_linear_graph_topological_sort(self):
        """Test topological sort on linear graph."""
        graph = self.create_linear_graph()
        traversal = GraphTraversal(graph)

        order = traversal.topological_sort()
        assert len(order) == 3
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_branching_graph_topological_sort(self):
        """Test topological sort on branching graph."""
        graph = self.create_branching_graph()
        traversal = GraphTraversal(graph)

        order = traversal.topological_sort()
        assert len(order) == 3
        # a must come before both b and c
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")

    def test_diamond_graph_topological_sort(self):
        """Test topological sort on diamond graph."""
        graph = self.create_diamond_graph()
        traversal = GraphTraversal(graph)

        order = traversal.topological_sort()
        assert len(order) == 4
        # a must be first
        assert order[0] == "a"
        # d must be last
        assert order[-1] == "d"

    def test_get_execution_order(self):
        """Test getting execution order from start node."""
        graph = self.create_linear_graph()
        traversal = GraphTraversal(graph)

        order = traversal.get_execution_order("a")
        assert order == ["a", "b", "c"]

    def test_get_execution_order_unreachable_node(self):
        """Test execution order doesn't include unreachable nodes."""
        nodes = [
            Node(id="a", type=NodeType.TRIGGER, label="A"),
            Node(id="b", type=NodeType.LLM_TASK, label="B"),
        ]
        edges = [Edge(source="a", target="b")]
        graph = Graph(version="1.0.0", nodes=nodes, edges=edges)
        traversal = GraphTraversal(graph)

        order = traversal.get_execution_order("a")
        assert "a" in order
        assert "b" in order

    def test_get_ready_nodes_initial(self):
        """Test getting ready nodes at start."""
        graph = self.create_linear_graph()
        traversal = GraphTraversal(graph)

        ready = traversal.get_ready_nodes(executed=set(), pending={"a", "b", "c"})
        # Only a has no predecessors
        assert ready == ["a"]

    def test_get_ready_nodes_after_first(self):
        """Test getting ready nodes after first execution."""
        graph = self.create_linear_graph()
        traversal = GraphTraversal(graph)

        ready = traversal.get_ready_nodes(executed={"a"}, pending={"b", "c"})
        # After a, b is ready
        assert ready == ["b"]

    def test_get_ready_nodes_after_second(self):
        """Test getting ready nodes after second execution."""
        graph = self.create_linear_graph()
        traversal = GraphTraversal(graph)

        ready = traversal.get_ready_nodes(executed={"a", "b"}, pending={"c"})
        assert ready == ["c"]

    def test_get_ready_nodes_branching(self):
        """Test ready nodes with branching."""
        graph = self.create_branching_graph()
        traversal = GraphTraversal(graph)

        ready = traversal.get_ready_nodes(executed=set(), pending={"a", "b", "c"})
        assert ready == ["a"]

        ready = traversal.get_ready_nodes(executed={"a"}, pending={"b", "c"})
        # Both b and c are ready after a
        assert set(ready) == {"b", "c"}

    def test_find_path_exists(self):
        """Test finding existing path."""
        graph = self.create_linear_graph()
        traversal = GraphTraversal(graph)

        path = traversal.find_path("a", "c")
        assert path == ["a", "b", "c"]

    def test_find_path_same_node(self):
        """Test finding path to same node."""
        graph = self.create_linear_graph()
        traversal = GraphTraversal(graph)

        path = traversal.find_path("a", "a")
        assert path == ["a"]

    def test_find_path_not_exists(self):
        """Test finding non-existent path."""
        nodes = [
            Node(id="a", type=NodeType.TRIGGER, label="A"),
            Node(id="b", type=NodeType.LLM_TASK, label="B"),
        ]
        edges = [Edge(source="a", target="b")]
        graph = Graph(version="1.0.0", nodes=nodes, edges=edges)
        traversal = GraphTraversal(graph)

        path = traversal.find_path("b", "a")
        assert path is None

    def test_validate_valid_graph(self):
        """Test validating a valid graph."""
        graph = self.create_linear_graph()
        graph.entryPoint = "a"
        traversal = GraphTraversal(graph)

        errors = traversal.validate()
        assert len(errors) == 0

    def test_validate_missing_entry_point(self):
        """Test validating graph with missing entry point."""
        graph = self.create_linear_graph()
        graph.entryPoint = "nonexistent"
        traversal = GraphTraversal(graph)

        errors = traversal.validate()
        assert any("Entry point" in e for e in errors)

    def test_validate_unreferenced_node(self):
        """Test validating graph with unreferenced node."""
        nodes = [
            Node(id="a", type=NodeType.TRIGGER, label="A"),
            Node(id="b", type=NodeType.LLM_TASK, label="B"),
            Node(id="orphan", type=NodeType.LLM_TASK, label="Orphan"),
        ]
        edges = [Edge(source="a", target="b")]
        graph = Graph(version="1.0.0", nodes=nodes, edges=edges, entryPoint="a")
        traversal = GraphTraversal(graph)

        errors = traversal.validate()
        assert any("not referenced" in e for e in errors)

    def test_validate_edge_to_nonexistent_node(self):
        """Test validating graph with edge to nonexistent node."""
        nodes = [Node(id="a", type=NodeType.TRIGGER, label="A")]
        edges = [Edge(source="a", target="nonexistent")]
        graph = Graph(version="1.0.0", nodes=nodes, edges=edges, entryPoint="a")
        traversal = GraphTraversal(graph)

        errors = traversal.validate()
        assert any("non-existent" in e for e in errors)

    def test_validate_disconnected_node(self):
        """Test validating graph with disconnected node."""
        nodes = [
            Node(id="a", type=NodeType.TRIGGER, label="A"),
            Node(id="b", type=NodeType.LLM_TASK, label="B"),
            Node(id="c", type=NodeType.LLM_TASK, label="C"),
        ]
        edges = [
            Edge(source="a", target="b"),
            # c is not connected to a
        ]
        graph = Graph(version="1.0.0", nodes=nodes, edges=edges, entryPoint="a")
        traversal = GraphTraversal(graph)

        errors = traversal.validate()
        assert any("not reachable" in e for e in errors)

    def test_get_subgraph(self):
        """Test extracting subgraph."""
        nodes = [
            Node(id="a", type=NodeType.TRIGGER, label="A"),
            Node(id="b", type=NodeType.LLM_TASK, label="B"),
            Node(id="c", type=NodeType.LLM_TASK, label="C"),
        ]
        edges = [
            Edge(source="a", target="b"),
            Edge(source="b", target="c"),
        ]
        graph = Graph(version="1.0.0", nodes=nodes, edges=edges, entryPoint="a")
        traversal = GraphTraversal(graph)

        subgraph = traversal.get_subgraph({"a", "b"})
        assert len(subgraph.nodes) == 2
        assert len(subgraph.edges) == 1
