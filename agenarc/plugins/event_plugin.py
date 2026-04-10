"""
Event Plugin Base Class

Base class for event-driven plugins that can trigger graph execution.
Event plugins listen for external events (QQ messages, webhooks, timers, etc.)
and trigger the graph when events arrive.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class EventPlugin(ABC):
    """
    Base class for event-driven plugins.

    Event plugins listen for external events and trigger graph execution
    by calling the provided callback function.

    Usage:
        class MyEventPlugin(EventPlugin):
            @property
            def name(self) -> str:
                return "my_event"

            async def start(self, trigger_callback: Callable[[Dict[str, Any]], None]):
                # Start listening for events
                # When event arrives, call trigger_callback(event_data)

        # Register in agenarc.json:
        {
            "name": "my_event",
            "version": "1.0.0",
            "entry": "plugin.py",
            "type": "event",
            "operators": ["MyEventPlugin"]
        }
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def description(self) -> str:
        """Plugin description."""
        return ""

    @abstractmethod
    async def start(self, trigger_callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Start listening for events.

        This method should start the event source (WebSocket, HTTP server, etc.)
        and call trigger_callback when events arrive.

        The trigger_callback expects a standardized event payload:
        {
            "source": str,        # Event source name (e.g., "qq", "webhook", "timer")
            "user_id": Any,       # User identifier (format depends on source)
            "group_id": Any,      # Group identifier (0 if not applicable)
            "message": Any,       # Message content (format depends on source)
            "raw": Any,           # Raw event data from source
            "timestamp": int      # Event timestamp (Unix seconds)
        }

        Args:
            trigger_callback: Function to call when an event is received.
                              The callback will trigger the graph execution.
        """
        pass

    async def stop(self) -> None:
        """
        Stop listening for events.

        Override this method to cleanup resources.
        """
        pass


class TriggerCallback:
    """
    Helper class to manage trigger callbacks and graph execution.
    """

    def __init__(
        self,
        engine: Any,
        state_manager: Optional[Any] = None,
        execution_mode: Any = None
    ):
        self.engine = engine
        self.state_manager = state_manager
        from agenarc.engine.executor import ExecutionMode
        self.execution_mode = execution_mode if execution_mode is not None else ExecutionMode.ASYNC
        self._running = False
        self._lock = asyncio.Lock()

    async def __call__(self, event_data: Dict[str, Any]) -> None:
        """
        Trigger callback - execute graph with event data as payload.

        Args:
            event_data: Standardized event payload
        """
        if not self._running:
            return

        async with self._lock:
            try:
                # Create fresh state for each execution
                from agenarc.engine.state import StateManager

                state = StateManager(
                    auto_checkpoint=self.engine.enable_checkpoint
                )
                state.initialize(
                    f"event_{event_data.get('timestamp', 0)}",
                    self.engine._graph.entryPoint if self.engine._graph else "agent"
                )

                # Attach state to engine
                self.engine._state = state

                # Execute with event payload
                result = await self.engine.execute(event_data, mode=self.execution_mode)

            except Exception as e:
                print(f"[TriggerCallback] Error executing graph: {e}")
                import traceback
                traceback.print_exc()

    def start(self) -> None:
        """Mark as running."""
        self._running = True

    def stop(self) -> None:
        """Mark as stopped."""
        self._running = False
