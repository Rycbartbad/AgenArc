"""
Graph Traversal

Graph traversal algorithms for AgenArc execution planning.
"""

from collections import deque
from typing import Callable, Dict, List, Optional, Set, Tuple

from agenarc.protocol.schema import Edge, Graph, Node


class CycleError(Exception):
    """Raised when a cycle is detected in the graph."""
    pass


class DisconnectedGraphError(Exception):
    """Raised when graph has nodes not reachable from entry point."""
    pass


class GraphTraversal:
    """
    Graph traversal utilities for execution planning.

    Provides:
    - Topological sorting (for execution order)
    - Reachability analysis
    - Cycle detection
    """

    def __init__(self, graph: Graph):
        self.graph = graph
        self._adjacency: Dict[str, List[str]] = {}
        self._reverse_adjacency: Dict[str, List[str]] = {}
        self._build_adjacency()

    def _build_adjacency(self) -> None:
        """Build adjacency lists from edges."""
        self._adjacency = {node.id: [] for node in self.graph.nodes}
        self._reverse_adjacency = {node.id: [] for node in self.graph.nodes}

        for edge in self.graph.edges:
            if edge.source in self._adjacency:
                self._adjacency[edge.source].append(edge.target)
            if edge.target in self._reverse_adjacency:
                self._reverse_adjacency[edge.target].append(edge.source)

    def topological_sort(self) -> List[str]:
        """
        Compute topological sort of the graph.

        Returns:
            List of node IDs in topological order

        Raises:
            CycleError: If graph contains a cycle
        """
        # Kahn's algorithm
        in_degree = {node.id: 0 for node in self.graph.nodes}
        for edge in self.graph.edges:
            in_degree[edge.target] += 1

        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)

            for neighbor in self._adjacency.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self.graph.nodes):
            raise CycleError("Graph contains a cycle")

        return result

    def get_execution_order(self, start_node_id: str) -> List[str]:
        """
        Get execution order starting from a specific node.

        Uses DFS to find all reachable nodes.

        Args:
            start_node_id: ID of the starting node

        Returns:
            List of node IDs in execution order
        """
        visited: Set[str] = set()
        order: List[str] = []

        def dfs(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            order.append(node_id)

            for neighbor in self._adjacency.get(node_id, []):
                dfs(neighbor)

        dfs(start_node_id)
        return order

    def get_ready_nodes(
        self,
        executed: Set[str],
        pending: Set[str]
    ) -> List[str]:
        """
        Get nodes that are ready to execute.

        A node is ready if:
        1. It's pending (not yet executed)
        2. All its predecessors have been executed

        Args:
            executed: Set of executed node IDs
            pending: Set of pending node IDs

        Returns:
            List of node IDs that can now execute
        """
        ready = []

        for node_id in pending:
            # Check if all predecessors are executed
            predecessors = self._reverse_adjacency.get(node_id, [])
            if all(pred in executed for pred in predecessors):
                ready.append(node_id)

        return ready

    def find_path(self, source: str, target: str) -> Optional[List[str]]:
        """
        Find a path from source to target.

        Args:
            source: Source node ID
            target: Target node ID

        Returns:
            List of node IDs forming the path, or None if no path exists
        """
        if source == target:
            return [source]

        visited: Set[str] = set()
        queue = deque([(source, [source])])

        while queue:
            node, path = queue.popleft()

            if node in visited:
                continue
            visited.add(node)

            for neighbor in self._adjacency.get(node, []):
                if neighbor == target:
                    return path + [neighbor]

                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))

        return None

    def get_subgraph(self, node_ids: Set[str]) -> Graph:
        """
        Extract a subgraph containing only the specified nodes.

        Args:
            node_ids: Set of node IDs to include

        Returns:
            New Graph with only the specified nodes and their connecting edges
        """
        # This would create a new graph with filtered nodes/edges
        # For now, return a new graph with same structure but filtered
        nodes = [n for n in self.graph.nodes if n.id in node_ids]
        edges = [e for e in self.graph.edges if e.source in node_ids and e.target in node_ids]

        new_graph = Graph(
            version=self.graph.version,
            metadata=self.graph.metadata,
            entryPoint=self.graph.entryPoint if self.graph.entryPoint in node_ids else "",
            nodes=nodes,
            edges=edges,
        )
        return new_graph

    def validate(self) -> List[str]:
        """
        Validate the graph structure.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check entry point exists
        if self.graph.entryPoint:
            if not self.graph.get_node(self.graph.entryPoint):
                errors.append(f"Entry point '{self.graph.entryPoint}' does not exist")

        # Check all nodes are referenced
        referenced_ids = {self.graph.entryPoint} if self.graph.entryPoint else set()
        for edge in self.graph.edges:
            referenced_ids.add(edge.source)
            referenced_ids.add(edge.target)

        for node in self.graph.nodes:
            if node.id not in referenced_ids:
                errors.append(f"Node '{node.id}' is not referenced by any edge")

        # Check for orphan edges
        node_ids = {n.id for n in self.graph.nodes}
        for edge in self.graph.edges:
            if edge.source not in node_ids:
                errors.append(f"Edge references non-existent source node '{edge.source}'")
            if edge.target not in node_ids:
                errors.append(f"Edge references non-existent target node '{edge.target}'")

        # Check for cycles
        try:
            self.topological_sort()
        except CycleError:
            errors.append("Graph contains a cycle")

        # Check for disconnected nodes (warning, not error)
        if self.graph.entryPoint:
            reachable = set(self.get_execution_order(self.graph.entryPoint))
            for node in self.graph.nodes:
                if node.id not in reachable and node.id != self.graph.entryPoint:
                    errors.append(f"Node '{node.id}' is not reachable from entry point")

        return errors
