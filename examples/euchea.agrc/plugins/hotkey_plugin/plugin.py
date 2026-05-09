"""
Hotkey Plugin for AgenArc

Listens for global Alt+A hotkey and triggers graph execution.
Ported from examples/euchea/euchea_serve.py into a self-contained event plugin.
"""

import asyncio
import threading
import time
from typing import Any, Callable, Dict, Optional


class HotkeyPlugin:
    """
    Global hotkey event plugin.

    Listens for Alt+A and calls trigger_callback with standardized event data.

    Configuration (in config.yaml -> plugins.hotkey.*):
        hotkey: Hotkey combination (default: "alt+a")
    """

    def __init__(self):
        self.name = "hotkey"
        self.version = "1.0.0"
        self.description = "Global Alt+A hotkey listener"

        self.hotkey: str = "Alt+A"

        self._trigger_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()

    def configure(self, config: Dict[str, Any]) -> None:
        """Apply configuration from config.yaml."""
        self.hotkey = config.get("hotkey", self.hotkey)

    async def start(self, trigger_callback: Callable[[Dict[str, Any]], None]) -> None:
        """Start listening for the hotkey."""
        if self._running:
            return

        self._trigger_callback = trigger_callback
        self._running = True
        self._stop_event.clear()
        self._loop = asyncio.get_running_loop()

        # Start hotkey listener in a background thread
        self._listener_thread = threading.Thread(
            target=self._run_listener,
            daemon=True,
        )
        self._listener_thread.start()

        print(f"[hotkey] 监听 {self.hotkey} ...  (Ctrl+C 退出)")

    async def stop(self) -> None:
        """Stop listening for the hotkey."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        print("[hotkey] 已停止")

    def _on_hotkey(self) -> None:
        """Called when hotkey is pressed."""
        if not self._running or self._loop is None:
            return

        print("\n[euchea] ===== Alt+A 触发 =====")

        event_data = {
            "source": "hotkey",
            "user_id": "keyboard",
            "group_id": 0,
            "message": f"Hotkey {self.hotkey} pressed",
            "message_type": "private",
            "raw": {"hotkey": self.hotkey},
            "timestamp": int(time.time()),
        }

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._trigger_callback(event_data), self._loop
            )
            # Wait up to 180s for execution to complete
            future.result(timeout=180)
        except Exception as e:
            print(f"[euchea] 执行失败: {e}")

    def _run_listener(self) -> None:
        """Run the hotkey listener in a separate thread."""
        try:
            import keyboard
        except ImportError:
            print(
                "[hotkey] 请安装 keyboard: pip install keyboard",
                flush=True,
            )
            return

        keyboard.add_hotkey(self.hotkey, self._on_hotkey)
        # Block until stop is requested
        self._stop_event.wait()
        # Cleanup
        try:
            keyboard.remove_hotkey(self.hotkey)
        except Exception:
            pass
