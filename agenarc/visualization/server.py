"""
Visualization Server

HTTP + WebSocket server for the visualization platform.
Provides REST API for graph operations and WebSocket for real-time updates.
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Set

from agenarc.engine.executor import ExecutionEngine
from agenarc.protocol.loader import ProtocolLoader
from agenarc.visualization.events import ExecutionEventEmitter, ExecutionEvent
from agenarc.visualization.state import GraphStateTracker, NodeStatus


class VisualizationServer:
    """
    HTTP + WebSocket server for visualization platform.

    Responsibilities:
    - Serve REST API endpoints for graph operations
    - Manage WebSocket connections for real-time updates
    - Bridge between frontend and ExecutionEngine
    """

    def __init__(
        self,
        engine: ExecutionEngine,
        host: str = "localhost",
        port: int = 8765
    ):
        self.engine = engine
        self.host = host
        self.port = port
        self._ws_connections: Set[Any] = set()
        self._event_emitter = ExecutionEventEmitter()
        self._state_tracker = GraphStateTracker()
        self._running = False
        self._server: Optional[Any] = None

    @property
    def event_emitter(self) -> ExecutionEventEmitter:
        """Get the event emitter."""
        return self._event_emitter

    @property
    def state_tracker(self) -> GraphStateTracker:
        """Get the state tracker."""
        return self._state_tracker

    async def start(self) -> None:
        """Start the visualization server."""
        self._running = True
        self._attach_to_engine()
        self._server = await asyncio.start_server(
            self._handle_http,
            self.host,
            self.port
        )
        addr = self._server.sockets[0].getsockname()
        print(f"[VISUALIZATION] Server started at http://{addr[0]}:{addr[1]}")

    async def stop(self) -> None:
        """Stop the visualization server."""
        self._running = False
        self._detach_from_engine()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        print("[VISUALIZATION] Server stopped")

    def _attach_to_engine(self) -> None:
        """Attach event hooks to ExecutionEngine."""
        # Hook into engine's node execution methods
        # This is done via monkey-patching for now
        original_execute_node = getattr(self.engine, '_execute_node', None)

        if original_execute_node:
            self._original_execute_node = original_execute_node

            async def hooked_execute_node(node, context):
                node_id = node.id
                exec_id = self.engine._execution_id or "unknown"
                self._state_tracker.update_node_status(node_id, NodeStatus.RUNNING)
                self._event_emitter.emit_node_start(node_id, exec_id)
                try:
                    result = await original_execute_node(node, context)
                    self._state_tracker.update_node_status(node_id, NodeStatus.COMPLETED)
                    self._state_tracker.record_node_output(node_id, result)
                    self._event_emitter.emit_node_complete(node_id, exec_id, result)
                    return result
                except Exception as e:
                    self._state_tracker.update_node_status(node_id, NodeStatus.FAILED)
                    self._event_emitter.emit_node_error(node_id, exec_id, str(e))
                    raise

            self.engine._execute_node = hooked_execute_node

    def _detach_from_engine(self) -> None:
        """Detach event hooks from ExecutionEngine."""
        if hasattr(self, '_original_execute_node'):
            self.engine._execute_node = self._original_execute_node

    async def _handle_http(self, reader: Any, writer: Any) -> None:
        """Handle HTTP requests."""
        try:
            request_line = await reader.readline()
            method, path, _ = request_line.decode().split()

            # Read headers
            headers = {}
            while True:
                line = await reader.readline()
                if line == b'\r\n':
                    break
                key, value = line.decode().strip().split(': ', 1)
                headers[key.lower()] = value

            # Read body if present
            content_length = int(headers.get('content-length', 0))
            body = await reader.read(content_length) if content_length > 0 else b''

            # Route handling
            response = await self._route_request(method, path, headers, body)

            writer.write(response)
            await writer.drain()
        except Exception as e:
            error_response = self._json_response({"error": str(e)}, status=500)
            writer.write(error_response)
            await writer.drain()
        finally:
            writer.close()

    async def _route_request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: bytes
    ) -> bytes:
        """Route HTTP request to appropriate handler."""
        # GET /api/graph
        if method == "GET" and path == "/api/graph":
            return self._json_response(self._get_graph())

        # POST /api/graph (save)
        elif method == "POST" and path == "/api/graph":
            data = json.loads(body) if body else {}
            return self._json_response(self._save_graph(data))

        # POST /api/execute
        elif method == "POST" and path == "/api/execute":
            data = json.loads(body) if body else {}
            result = await self._execute_graph(data)
            return self._json_response(result)

        # POST /api/execute/stop
        elif method == "POST" and path == "/api/execute/stop":
            self._stop_execution()
            return self._json_response({"status": "stopped"})

        # GET /api/execution/status
        elif method == "GET" and path == "/api/execution/status":
            return self._json_response(self._get_execution_status())

        # GET /api/node/{id}/outputs
        elif method == "GET" and path.startswith("/api/node/"):
            parts = path.split('/')
            if len(parts) >= 4 and parts[3]:
                node_id = parts[3]
                return self._json_response(self._get_node_outputs(node_id))

        # GET /api/context
        elif method == "GET" and path == "/api/context":
            return self._json_response(self._get_context_state())

        # WebSocket upgrade
        elif method == "GET" and path == "/ws":
            return self._websocket_response(headers)

        # Health check
        elif method == "GET" and path == "/health":
            return self._json_response({"status": "ok"})

        # Not found
        return self._json_response({"error": "Not found"}, status=404)

    def _get_graph(self) -> Dict[str, Any]:
        """Get current graph data."""
        if not self.engine._graph:
            return {"version": "1.0.0", "nodes": [], "edges": []}

        graph = self.engine._graph
        return {
            "version": graph.version,
            "errorNode": graph.errorNode,
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type.value,
                    "label": n.label,
                    "description": n.description,
                    "inputs": [{"name": p.name, "type": p.type, "description": p.description, "default": p.default} for p in n.inputs],
                    "outputs": [{"name": p.name, "type": p.type, "description": p.description, "default": p.default} for p in n.outputs],
                    "config": n.config.data if hasattr(n.config, 'data') else {},
                    "errorHandling": {
                        "strategy": n.errorHandling.strategy.value if n.errorHandling else None,
                        "maxRetries": n.errorHandling.maxRetries if n.errorHandling else None,
                        "fallbackNode": n.errorHandling.fallbackNode if n.errorHandling else None,
                    } if n.errorHandling else None,
                    "checkpoint": n.checkpoint,
                    "idempotent": n.idempotent,
                }
                for n in graph.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "sourcePort": e.sourcePort,
                    "target": e.target,
                    "targetPort": e.targetPort,
                    "label": e.label,
                    "style": e.style,
                }
                for e in graph.edges
            ]
        }

    def _save_graph(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save graph data."""
        # TODO: Implement save to file
        return {"success": True}

    async def _execute_graph(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Start graph execution."""
        execution_id = str(uuid.uuid4())
        initial_inputs = data.get("initialInputs", {})

        # Start execution
        self._state_tracker.start_execution(execution_id)
        self._event_emitter.emit_execution_start(execution_id)

        # Run in background
        asyncio.create_task(self._run_execution(execution_id, initial_inputs))

        return {
            "executionId": execution_id,
            "status": "running"
        }

    async def _run_execution(
        self,
        execution_id: str,
        initial_inputs: Dict[str, Any]
    ) -> None:
        """Run graph execution."""
        try:
            result = await self.engine.execute(initial_inputs)
            self._state_tracker.end_execution(result.status)
            self._event_emitter.emit_execution_end(execution_id, result.status)
        except Exception as e:
            self._state_tracker.end_execution("failed")
            self._event_emitter.emit_execution_end(execution_id, "failed")

    def _stop_execution(self) -> None:
        """Stop current execution."""
        self.engine.stop()
        self._state_tracker.end_execution("stopped")

    def _get_execution_status(self) -> Dict[str, Any]:
        """Get current execution status."""
        state = self._state_tracker.get_current_state()
        return {
            "status": state.status,
            "executionId": state.execution_id,
            "currentNodeId": state.current_node_id,
            "startTime": state.start_time,
            "endTime": state.end_time,
            "nodeStatuses": {k: v.value for k, v in state.node_statuses.items()},
        }

    def _get_node_outputs(self, node_id: str) -> Dict[str, Any]:
        """Get outputs for a specific node."""
        outputs = self._state_tracker.get_node_outputs(node_id)
        status = self._state_tracker.get_node_status(node_id)
        return {
            "nodeId": node_id,
            "outputs": outputs,
            "status": status.value,
        }

    def _get_context_state(self) -> Dict[str, Any]:
        """Get current context state."""
        return self._state_tracker.get_context_snapshot()

    def _websocket_response(self, headers: Dict[str, str]) -> bytes:
        """Generate WebSocket upgrade response."""
        # Simplified - actual implementation needs proper WS handshake
        response = (
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"\r\n"
        )
        return response

    def _json_response(
        self,
        data: Dict[str, Any],
        status: int = 200
    ) -> bytes:
        """Generate JSON HTTP response."""
        body = json.dumps(data).encode()
        response = (
            f"HTTP/1.1 {status} OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"\r\n"
        ).encode() + body
        return response

    async def broadcast(self, event: Dict[str, Any]) -> None:
        """Broadcast event to all connected WebSocket clients."""
        # TODO: Implement WebSocket broadcasting
        pass
