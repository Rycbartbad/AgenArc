"""
QQ Plugin for AgenArc

Listens to QQ messages via NapCat WebSocket and triggers graph execution.
Supports OneBot v11 protocol.
"""

import asyncio
import json
import logging
import signal
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class QQPlugin:
    """
    QQ Event Plugin

    Connects to NapCat via WebSocket to receive QQ messages.
    When a message is received, it calls the trigger_callback with standardized event data.

    Configuration (in agenarc.json):
        ws_url: WebSocket connection address (default: ws://127.0.0.1:3001)
        auto_reconnect: Auto reconnect on disconnect (default: true)
        reconnect_interval: Reconnect interval in seconds (default: 5)
        filter_groups: List of group IDs to accept (empty = accept all)
        filter_users: List of user IDs to accept (empty = accept all)
        accept_private: Accept private messages (default: true)
        accept_group: Accept group messages (default: true)
    """

    def __init__(self):
        self.name = "qq"
        self.version = "1.0.0"
        self.description = "QQ event listener via NapCat WebSocket (OneBot v11)"

        # Configuration
        self.ws_url: str = "ws://127.0.0.1:3001"
        self.token: str = ""  # NapCat token (if required)
        self.auto_reconnect: bool = True
        self.reconnect_interval: int = 5
        self.filter_groups: List[int] = []
        self.filter_users: List[int] = []
        self.accept_private: bool = True
        self.accept_group: bool = True

        # Internal state
        self._trigger_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._ws_connection: Optional[Any] = None
        self._running: bool = False
        self._connected_logged: bool = False
        self._ws_url_with_token: str = ""

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the plugin from agenarc.json config."""
        self.ws_url = config.get("ws_url", self.ws_url)
        self.token = config.get("token", self.token)
        self.auto_reconnect = config.get("auto_reconnect", self.auto_reconnect)
        self.reconnect_interval = config.get("reconnect_interval", self.reconnect_interval)
        self.filter_groups = config.get("filter_groups", self.filter_groups)
        self.filter_users = config.get("filter_users", self.filter_users)
        self.accept_private = config.get("accept_private", self.accept_private)
        self.accept_group = config.get("accept_group", self.accept_group)

    @property
    def config_schema(self) -> Dict[str, Any]:
        """Return configuration schema for documentation."""
        return {
            "ws_url": {
                "type": "string",
                "default": "ws://127.0.0.1:3001",
                "description": "NapCat WebSocket address"
            },
            "token": {
                "type": "string",
                "default": "",
                "description": "NapCat token (if required, found in NapCat webui config)"
            },
            "auto_reconnect": {
                "type": "boolean",
                "default": True,
                "description": "Auto reconnect on disconnect"
            },
            "reconnect_interval": {
                "type": "integer",
                "default": 5,
                "description": "Reconnect interval in seconds"
            },
            "filter_groups": {
                "type": "array",
                "items": {"type": "integer"},
                "default": [],
                "description": "Only accept messages from these group IDs"
            },
            "filter_users": {
                "type": "array",
                "items": {"type": "integer"},
                "default": [],
                "description": "Only accept messages from these user IDs"
            },
            "accept_private": {
                "type": "boolean",
                "default": True,
                "description": "Accept private messages"
            },
            "accept_group": {
                "type": "boolean",
                "default": True,
                "description": "Accept group messages"
            }
        }

    async def start(self, trigger_callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Start listening for QQ messages.

        Args:
            trigger_callback: Function to call when message is received.
                              Will be called with standardized event data.
        """
        # Prevent multiple starts
        if self._running:
            return

        self._running = True
        self._trigger_callback = trigger_callback
        self._stop_event = asyncio.Event()
        self._connected_logged = False

        print(f"[QQ Plugin] Starting listener for {self.ws_url}...")

        # Start listener task
        self._listener_task = asyncio.create_task(self._listen_websocket())

        # Wait for stop signal
        await self._stop_event.wait()

        print("[QQ Plugin] Stopped.")

    async def stop(self) -> None:
        """Stop listening for QQ messages."""
        print("[QQ Plugin] stop() called")
        if not self._running:
            print("[QQ Plugin] stop() - not running")
            return

        self._running = False

        # Set stop event first
        if self._stop_event:
            self._stop_event.set()

        # Cancel the listener task directly - websockets doesn't exit cleanly on close()
        if self._listener_task:
            print("[QQ Plugin] stop() - cancelling listener task")
            self._listener_task.cancel()
            try:
                await asyncio.wait_for(self._listener_task, timeout=3.0)
            except asyncio.CancelledError:
                print("[QQ Plugin] stop() - task cancelled successfully")
            except asyncio.TimeoutError:
                print("[QQ Plugin] stop() - task did not respond to cancel")
            except Exception as e:
                print(f"[QQ Plugin] stop() - task error: {e}")

        # Now close websocket if still open
        if self._ws_connection:
            print("[QQ Plugin] stop() - closing websocket")
            try:
                self._ws_connection.close()
            except Exception:
                pass

        print("[QQ Plugin] stop() complete")

    async def _listen_websocket(self) -> None:
        """Main WebSocket listening loop."""
        reconnect_count = 0
        while not self._stop_event.is_set():
            try:
                import websockets

                # Build URL with token (NapCat uses access_token query param)
                ws_url = self.ws_url
                if self.token:
                    separator = "&" if "?" in ws_url else "?"
                    ws_url = f"{ws_url}{separator}access_token={self.token}"

                async with websockets.connect(ws_url, ping_interval=30) as ws:
                    self._ws_connection = ws
                    reconnect_count += 1
                    if reconnect_count == 1:
                        print(f"[QQ Plugin] Connected to {self.ws_url}")
                    else:
                        print(f"[QQ Plugin] Reconnected to {self.ws_url} (attempt #{reconnect_count})")

                    async for raw_message in ws:
                        if self._stop_event.is_set():
                            break
                        print(f"[QQ Plugin] Received: {raw_message[:80]}...")
                        await self._handle_message(raw_message)

            except ImportError:
                print("[QQ Plugin] Error: websockets library not installed.")
                print("[QQ Plugin] Run: pip install websockets")
                self._stop_event.set()
                break
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                print("[QQ Plugin] CancelledError caught - exiting")
                return
            except Exception as e:
                if not self._stop_event.is_set():
                    if reconnect_count == 1:
                        print(f"[QQ Plugin] Connection error: {e}")
                    if self.auto_reconnect:
                        print(f"[QQ Plugin] Reconnecting in {self.reconnect_interval}s...")
                        await asyncio.sleep(self.reconnect_interval)
                    else:
                        print("[QQ Plugin] Auto-reconnect disabled, stopping.")
                        self._stop_event.set()
                        break

    async def _handle_message(self, raw_message: str) -> None:
        """Process received WebSocket message and trigger callback."""
        try:
            event = json.loads(raw_message)

            # Only process message events
            if event.get("post_type") != "message":
                return

            message_type = event.get("message_type", "")

            # Check message type filter
            if message_type == "private" and not self.accept_private:
                return
            if message_type == "group" and not self.accept_group:
                return

            # Check group filter
            group_id = event.get("group_id", 0)
            if self.filter_groups and group_id not in self.filter_groups:
                return

            # Check user filter
            user_id = event.get("user_id", 0)
            if self.filter_users and user_id not in self.filter_users:
                return

            # Parse message content
            message_segments = event.get("message", [])
            if isinstance(message_segments, list):
                message_text = self._extract_text_from_segments(message_segments)
            else:
                message_text = str(message_segments)

            # Build standardized event payload
            standardized_event = {
                "source": "qq",
                "user_id": user_id,
                "group_id": group_id,
                "message": message_text,
                "message_type": message_type,
                "sender": event.get("sender", {}),
                "raw": event,
                "timestamp": event.get("time", 0),
                "token": self.token,  # Pass token for use in graph
            }

            print(f"[QQ Plugin] Received: [{message_type}] {user_id} -> {message_text[:50]}...")

            # Trigger graph execution
            if self._trigger_callback:
                print(f"[QQ Plugin] Calling trigger_callback...")
                await self._trigger_callback(standardized_event)
                print(f"[QQ Plugin] trigger_callback completed")
            else:
                print("[QQ Plugin] No trigger_callback set!")

        except json.JSONDecodeError as e:
            print(f"[QQ Plugin] Failed to parse message: {e}")

    def _extract_text_from_segments(self, segments: List[Dict]) -> str:
        """Extract plain text from OneBot message segments."""
        text_parts = []
        for segment in segments:
            seg_type = segment.get("type")
            data = segment.get("data", {})

            if seg_type == "text":
                text_parts.append(data.get("text", ""))
            elif seg_type == "image":
                text_parts.append("[图片]")
            elif seg_type == "at":
                text_parts.append(f"@{data.get('qq', '')}")
            elif seg_type == "face":
                text_parts.append(f"[表情:{data.get('id', '')}]")
            elif seg_type == "record":
                text_parts.append("[语音]")
            elif seg_type == "video":
                text_parts.append("[视频]")
            elif seg_type == "music":
                text_parts.append("[音乐]")
            elif seg_type == "reply":
                text_parts.append(f"[回复:{data.get('id', '')}]")
            else:
                # For unknown types, try to extract any text
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, str):
                            text_parts.append(value)

        return "".join(text_parts).strip()
