"""
Visualization Server

HTTP + WebSocket server for the visualization platform.
Provides REST API for graph operations and WebSocket for real-time updates.
"""

import asyncio
import json
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Set
from urllib.parse import parse_qs, urlparse

from agenarc.engine.executor import ExecutionEngine
from agenarc.protocol.loader import ProtocolLoader
from agenarc.visualization.events import ExecutionEventEmitter, ExecutionEvent
from agenarc.visualization.state import GraphStateTracker, NodeStatus


class LiveBuffer:
    """Thread-safe line buffer for real-time stdout capture."""
    def __init__(self):
        self._lines = []
    def write(self, text):
        if text:
            self._lines.append(text)
    def flush(self):
        pass
    def get_since(self, index):
        return self._lines[index:]
    @property
    def length(self):
        return len(self._lines)


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
        port: int = 8765,
        bundle_path: Optional[str] = None,
    ):
        self.engine = engine
        self.host = host
        self.port = port
        self.bundle_path = bundle_path
        self._ws_connections: Set[Any] = set()
        self._event_emitter = ExecutionEventEmitter()
        self._state_tracker = GraphStateTracker()
        self._running = False
        self._server: Optional[Any] = None
        self._session_state: Any = None  # Persistent state for multi-turn
        self._is_serving = False
        self._serve_status = {"status": "stopped", "plugins": [], "error": None}
        self._last_event_result: Optional[Dict[str, Any]] = None
        self._event_seq = 0
        self._serve_buffer: Optional[LiveBuffer] = None
        self._serve_buffer_idx = 0

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
        host_str = addr[0]
        # Normalize IPv6 loopback for display
        if host_str == "::1":
            host_str = "127.0.0.1"
        elif host_str == "::":
            host_str = self.host
        print(f"\n  [VISUALIZATION] Server started at http://{host_str}:{addr[1]}")
        print(f"  [VISUALIZATION] Open http://{host_str}:{addr[1]} in your browser\n")

        # Keep running until stopped
        await self._server.serve_forever()

    async def stop(self) -> None:
        """Stop the visualization server."""
        self._running = False
        self._detach_from_engine()
        if self._server:
            try:
                self._server.close()
                await asyncio.wait_for(self._server.wait_closed(), timeout=5)
            except (AttributeError, asyncio.TimeoutError, Exception):
                # Windows proactor may have None sock on cleanup; ignore
                pass
        print("[VISUALIZATION] Server stopped")

    def _attach_to_engine(self) -> None:
        """Attach event hooks to ExecutionEngine."""
        # Hook into engine's node execution methods
        original_execute = getattr(self.engine, '_execute_node_with_tracking', None)

        if original_execute:
            self._original_execute_node = original_execute

            async def hooked_execute_node(node):
                node_id = node.id
                exec_id = self.engine._execution_id or "unknown"
                self._state_tracker.update_node_status(node_id, NodeStatus.RUNNING)
                self._event_emitter.emit_node_start(node_id, exec_id)
                try:
                    result = await original_execute(node)
                    self._state_tracker.update_node_status(node_id, NodeStatus.COMPLETED)
                    self._state_tracker.record_node_output(node_id, result)
                    self._event_emitter.emit_node_complete(node_id, exec_id, result)
                    return result
                except Exception as e:
                    self._state_tracker.update_node_status(node_id, NodeStatus.FAILED)
                    self._event_emitter.emit_node_error(node_id, exec_id, str(e))
                    raise

            self.engine._execute_node_with_tracking = hooked_execute_node

    def _detach_from_engine(self) -> None:
        """Detach event hooks from ExecutionEngine."""
        if hasattr(self, '_original_execute_node'):
            self.engine._execute_node_with_tracking = self._original_execute_node

    async def _handle_http(self, reader: Any, writer: Any) -> None:
        """Handle HTTP requests."""
        try:
            request_line = await reader.readline()
            if not request_line or request_line.strip() == b'':
                writer.close()
                return
            parts = request_line.decode().strip().split()
            if len(parts) < 2:
                writer.close()
                return
            method = parts[0]
            path = parts[1]

            # Read headers
            headers = {}
            while True:
                line = await reader.readline()
                if line == b'\r\n':
                    break
                decoded = line.decode().strip()
                if ':' in decoded:
                    key, value = decoded.split(':', 1)
                    headers[key.lower().strip()] = value.strip()

            # Read body if present
            content_length = int(headers.get('content-length', 0))
            body = await reader.read(content_length) if content_length > 0 else b''

            # Route handling
            response = await self._route_request(method, path, headers, body)

            writer.write(response)
            await writer.drain()
        except Exception as e:
            try:
                error_response = self._json_response({"error": str(e)}, status=500)
                writer.write(error_response)
                await writer.drain()
            except Exception:
                pass
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def _route_request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: bytes
    ) -> bytes:
        """Route HTTP request to appropriate handler."""
        # CORS preflight
        if method == "OPTIONS":
            return self._json_response({"ok": True})

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

        # GET /api/execution/log?since=N (live serve mode log lines)
        elif method == "GET" and path.startswith("/api/execution/log"):
            parsed = urlparse(path)
            qs = parse_qs(parsed.query)
            since = int(qs.get("since", ["0"])[0])
            buf = self._serve_buffer
            if buf:
                lines = buf.get_since(since)
                return self._json_response({"lines": lines, "next": buf.length})
            return self._json_response({"lines": [], "next": 0})

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

        # GET /api/execution/last (last event-triggered execution result)
        elif method == "GET" and path == "/api/execution/last":
            return self._json_response(self._last_event_result or {"status": "none"})

        # WebSocket upgrade
        elif method == "GET" and path == "/ws":
            return self._websocket_response(headers)

        # Health check
        elif method == "GET" and path == "/health":
            vfs_path = None
            if self.bundle_path:
                vfs_path = f"agrc://  {self.bundle_path}"
            return self._json_response({
                "status": "ok",
                "vfs": vfs_path,
                "bundlePath": str(self.bundle_path) if self.bundle_path else None,
                "nodeCount": len(self.engine._graph.nodes) if self.engine._graph else 0,
                "edgeCount": len(self.engine._graph.edges) if self.engine._graph else 0,
            })

        # GET /api/serve (status) and POST /api/serve (start)
        elif path == "/api/serve":
            if method == "GET":
                return self._json_response(self._serve_status)
            elif method == "POST":
                try:
                    result = await self._start_service()
                    return self._json_response(result)
                except Exception as e:
                    self._serve_status["status"] = "error"
                    self._serve_status["error"] = str(e)
                    return self._json_response(self._serve_status, status=500)

        # Serve static frontend
        elif method == "GET" and (path == "/" or path == "/index.html"):
            return await self._serve_static("index.html", "text/html")

        # Not found — serve frontend for SPA routing
        return self._json_response({"error": "Not found"}, status=404)

    async def _start_service(self) -> Dict[str, Any]:
        """Start event plugins in service mode (like CLI's `agenarc serve`).

        Returns:
            Dict with status and started plugin info
        """
        from agenarc.plugins.event_plugin import TriggerCallback

        if self._is_serving:
            return self._serve_status

        engine = self.engine
        pm = engine.plugin_manager
        if not pm:
            self._serve_status = {"status": "error", "plugins": [], "error": "No plugin manager"}
            return self._serve_status

        # Find Plugin source nodes
        source_nodes = []
        if hasattr(engine, '_find_source_nodes'):
            source_nodes = engine._find_source_nodes()

        # Detect event plugins from source nodes
        detected = []
        for node in source_nodes:
            if hasattr(node.type, 'value') and node.type.value == "Plugin":
                config = node.metadata.get("config", {})
                plugin_name = config.get("plugin", "")
                if plugin_name and plugin_name not in [d["name"] for d in detected]:
                    detected.append({"node": node.id, "name": plugin_name})

        if not detected:
            self._serve_status = {"status": "idle", "plugins": [], "error": None}
            return self._serve_status

        import importlib
        import importlib.util as _util
        import json as _json

        # Create live buffer for stdout capture during serve
        self._serve_buffer = LiveBuffer()

        # Create trigger callback with result capture
        original_trigger = TriggerCallback(engine)
        original_trigger.start()

        async def trigger_with_capture(event_data):
            import sys as _sys
            import uuid
            buf = self._serve_buffer
            buf_idx_before = buf.length
            old_stdout = _sys.stdout
            _sys.stdout = buf
            # Start execution tracking
            exec_id = str(uuid.uuid4())
            self._state_tracker.start_execution(exec_id)
            try:
                await original_trigger(event_data)
            except Exception as e:
                _sys.stdout = old_stdout
                print(f"[Serve] Graph execution error: {e}")
                import traceback
                traceback.print_exc()
                _sys.stdout = buf
            finally:
                _sys.stdout = old_stdout
                self._state_tracker.end_execution("completed")
            # Store last result for frontend polling
            try:
                if engine._state and hasattr(engine._state, '_local'):
                    node_outputs = {}
                    errors = []
                    for node_id, data in engine._state._local.items():
                        if isinstance(data, dict) and "_outputs" in data:
                            out = data["_outputs"]
                            node_outputs[node_id] = out
                            if out.get("success") is False and out.get("error"):
                                errors.append(f"{node_id}: {out['error']}")
                    self._event_seq += 1
                    captured = "".join(buf.get_since(buf_idx_before))
                    self._last_event_result = {
                        "id": self._event_seq,
                        "status": "executed",
                        "timestamp": __import__('time').time(),
                        "node_outputs": node_outputs,
                        "errors": errors,
                        "log": captured,
                    }
            except Exception:
                pass

        started = []
        for p in detected:
            plugin_name = p["name"]
            plugin_instance = None

            # Try loading via PluginManager's discovered plugins
            plugin_info = pm._plugins.get(plugin_name)
            if plugin_info and plugin_info.path:
                manifest_path = plugin_info.path
                if manifest_path.name != "agenarc.json":
                    manifest_path = manifest_path.parent / "agenarc.json"
                if manifest_path.exists():
                    try:
                        manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
                        entry = manifest.get("entry", "plugin.py")
                        entry_path = manifest_path.parent / entry
                        if entry_path.exists():
                            ops = manifest.get("operators", [])
                            if ops:
                                spec = _util.spec_from_file_location(
                                    f"_serve_plugin_{plugin_name}", entry_path
                                )
                                if spec and spec.loader:
                                    module = _util.module_from_spec(spec)
                                    spec.loader.exec_module(module)
                                    first_op = ops[0]
                                    op_name = first_op if isinstance(first_op, str) else first_op.get("name")
                                    if op_name:
                                        plugin_instance = getattr(module, op_name)()
                    except Exception:
                        pass

            if plugin_instance is None:
                continue

            # Configure
            if hasattr(plugin_instance, 'configure'):
                try:
                    from agenarc.config import get_config
                    cfg = get_config()
                    plugin_cfg = cfg.get(f"plugins.{plugin_name}", {})
                    plugin_instance.configure(plugin_cfg)
                except Exception:
                    pass

            # Register and start
            pm.register_event_plugin(plugin_name, plugin_instance)
            await pm.start_event_plugin(plugin_name, trigger_with_capture)
            started.append(plugin_name)

        if started:
            engine._event_trigger_callback = trigger_with_capture
            self._is_serving = True

        self._serve_status = {
            "status": "running" if started else "idle",
            "plugins": started,
            "error": None,
        }
        return self._serve_status

    def _node_to_dict(self, n: Any) -> Dict[str, Any]:
        """Convert a Node to a dict. Plugin ports from agenarc.json manifest."""
        base = {
            "id": n.id,
            "type": n.type.value if hasattr(n.type, 'value') else str(n.type),
            "label": getattr(n, 'label', ''),
            "config": n.config.data if hasattr(n, 'config') and hasattr(n.config, 'data') else {},
            "inputs": [],
            "outputs": [],
        }
        is_join = n.type.value == "Join"

        # For Plugin nodes, read ports from agenarc.json manifest
        if n.type.value == "Plugin":
            try:
                config = n.config.data if hasattr(n, 'config') and hasattr(n.config, 'data') else {}
                plugin_name = config.get("plugin", "")
                function_name = config.get("function", "")
                if plugin_name and self.engine.plugin_manager:
                    manifest = self.engine.plugin_manager.get_plugin_manifest(plugin_name)
                    if manifest and "operators" in manifest:
                        for op in manifest["operators"]:
                            if isinstance(op, dict):
                                if not function_name or op.get("name") == function_name:
                                    base["inputs"] = op.get("inputs", [])
                                    base["outputs"] = op.get("outputs", [])
                                    return base
                            elif isinstance(op, str) and (not function_name or op == function_name):
                                return base
            except Exception:
                pass
            return base

        # For Join nodes, output ports are dynamic based on incoming edges (passthrough)
        if is_join:
            try:
                if self.engine._graph and hasattr(self.engine._graph, 'edges'):
                    dynamic_out = []
                    seen = set()
                    for edge in self.engine._graph.edges:
                        if edge.target == n.id:
                            src_node = self.engine._graph.get_node(edge.source)
                            source_ports = []
                            if src_node:
                                src_dict = self._node_to_dict(src_node)
                                source_ports = [p["name"] for p in src_dict.get("outputs", [])]
                            if edge.sourcePort:
                                ports_to_add = [edge.sourcePort]
                            else:
                                ports_to_add = source_ports
                            for p in ports_to_add:
                                out_name = f"{edge.source}_{p}"
                                if out_name not in seen:
                                    seen.add(out_name)
                                    dynamic_out.append({"name": out_name, "type": "any"})
                    if dynamic_out:
                        base["outputs"] = dynamic_out
                        return base
            except Exception:
                pass
            # Fall through to operator-based ports if no dynamic ports detected

        # For all other node types, get ports from operator
        try:
            operator = self.engine.get_operator(n)
            if operator:
                inp_ports = operator.get_input_ports()
                out_ports = operator.get_output_ports()
                if inp_ports:
                    base["inputs"] = [{"name": p.name, "type": p.type} for p in inp_ports]
                if out_ports:
                    base["outputs"] = [{"name": p.name, "type": p.type} for p in out_ports]
        except Exception:
            pass

        return base

    def _get_graph(self) -> Dict[str, Any]:
        """Get current graph data."""
        if not self.engine._graph:
            return {"version": "1.0.0", "nodes": [], "edges": []}

        graph = self.engine._graph
        try:
            return {
                "version": getattr(graph, 'version', '1.0.0'),
                "bundlePath": str(self.bundle_path) if self.bundle_path else None,
                "nodes": [
                    self._node_to_dict(n)
                    for n in (getattr(graph, 'nodes', []) or [])
                ],
                "edges": [
                    {
                        "source": e.source,
                        "sourcePort": getattr(e, 'sourcePort', ''),
                        "target": e.target,
                        "targetPort": getattr(e, 'targetPort', ''),
                    }
                    for e in (getattr(graph, 'edges', []) or [])
                ]
            }
        except Exception:
            return {"version": "1.0.0", "nodes": [], "edges": []}

    def _save_graph(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save graph data — update engine state with frontend changes."""
        try:
            if self.engine._graph and "nodes" in data:
                # Update existing graph nodes with frontend positions
                # The engine keeps canonical node definitions; frontend adds layout
                pass
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_graph(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute graph synchronously and return full results."""
        if not self.engine._graph or not self.engine._graph.nodes:
            return {"error": "No graph loaded", "status": "failed"}

        from agenarc.engine.executor import NodeStatus as EngineNodeStatus
        from agenarc.engine.state import StateManager

        execution_id = str(uuid.uuid4())
        initial_inputs = data.get("initialInputs", {})

        # Initialize persistent session state for multi-turn conversations
        if self._session_state is None:
            self._session_state = StateManager(auto_checkpoint=False)
            source_nodes = self.engine._find_source_nodes()
            graph_id = source_nodes[0].id if source_nodes else "graph"
            self._session_state.initialize(execution_id, graph_id)
            self._session_state.set_global("_session_first_run", True)
        else:
            self._session_state.set_global("_session_first_run", False)

        # Attach session state to engine so it reuses it across calls
        self.engine._state = self._session_state

        self._state_tracker.start_execution(execution_id)
        self._event_emitter.emit_execution_start(execution_id)

        try:
            result = await asyncio.wait_for(
                self.engine.execute(initial_inputs),
                timeout=300
            )

            # Record all node outputs in state tracker
            for node_id, exec_res in result.node_results.items():
                if exec_res.status == EngineNodeStatus.COMPLETED:
                    self._state_tracker.update_node_status(
                        node_id, NodeStatus.COMPLETED
                    )
                    self._state_tracker.record_node_output(
                        node_id, exec_res.outputs
                    )

            self._state_tracker.end_execution(result.status)
            self._event_emitter.emit_execution_end(execution_id, result.status)

            return {
                "status": result.status,
                "executionId": execution_id,
                "finalOutputs": result.final_outputs,
                "nodeResults": {
                    nid: {
                        "status": er.status.value,
                        "outputs": er.outputs,
                        "error": str(er.error) if er.error else None,
                        "durationMs": er.duration_ms,
                    }
                    for nid, er in result.node_results.items()
                },
                "durationMs": result.duration_ms,
            }
        except asyncio.TimeoutError:
            self._state_tracker.end_execution("timeout")
            return {"status": "timeout", "error": "Execution timed out"}
        except Exception as e:
            self._state_tracker.end_execution("failed")
            self._event_emitter.emit_execution_end(execution_id, "failed")
            return {"status": "failed", "error": str(e)}

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

    async def _serve_static(self, filename: str, mime: str) -> bytes:
        """Serve a static file from the visualization/static directory."""
        static_dir = Path(__file__).parent / "static"
        filepath = static_dir / filename

        try:
            if not filepath.exists() or not filepath.is_file():
                return self._json_response(
                    {"error": f"Static file '{filename}' not found"},
                    status=404
                )

            # Handle text files with encoding
            if mime.startswith("text/") or mime == "application/javascript":
                body = filepath.read_bytes()
            else:
                body = filepath.read_bytes()

            status_line = "HTTP/1.1 200 OK\r\n"
            headers = (
                f"Content-Type: {mime}\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"Cache-Control: no-cache\r\n"
                f"\r\n"
            )
            return (status_line + headers).encode() + body
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)

    def _json_response(
        self,
        data: Dict[str, Any],
        status: int = 200
    ) -> bytes:
        """Generate JSON HTTP response."""
        body = json.dumps(data, ensure_ascii=False).encode()
        status_text = "OK" if status == 200 else "Not Found" if status == 404 else "Internal Server Error"
        response = (
            f"HTTP/1.1 {status} {status_text}\r\n"
            f"Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            f"Access-Control-Allow-Headers: Content-Type\r\n"
            f"\r\n"
        ).encode() + body
        return response

    async def broadcast(self, event: Dict[str, Any]) -> None:
        """Broadcast event to all connected WebSocket clients."""
        # TODO: Implement WebSocket broadcasting
        pass
