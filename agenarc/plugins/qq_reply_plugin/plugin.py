"""
QQ Reply Plugin for AgenArc

Provides QQ message sending functionality via NapCat WebSocket.
Uses a shared connection manager to avoid short-connection issues.
"""

import asyncio
import json
from typing import Any, Dict, Optional

from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port


class QQConnectionManager:
    """
    Singleton manager for QQ WebSocket connections.

    Maintains a shared connection to NapCat to avoid the "WebSocket is not open"
    error that occurs when using short-lived connections.
    """

    _instance: Optional['QQConnectionManager'] = None
    _ws_connection: Optional[Any] = None
    _lock: asyncio.Lock = None
    _ws_url: str = "ws://127.0.0.1:3001"
    _token: str = ""

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._lock = asyncio.Lock()
        return cls._instance

    @classmethod
    def configure(cls, ws_url: str, token: str = ""):
        """Configure the connection manager."""
        cls._ws_url = ws_url
        cls._token = token

    @classmethod
    def _load_config(cls):
        """Load config from agenarc config file."""
        import os
        from pathlib import Path
        config_path = Path.home() / ".agenarc" / "config.yaml"
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            qq_config = config.get("plugins", {}).get("qq", {})
            cls._ws_url = qq_config.get("ws_url", cls._ws_url)
            cls._token = qq_config.get("token", cls._token)

    @classmethod
    async def get_connection(cls) -> Any:
        """Get or create the shared WebSocket connection."""
        if cls._lock is None:
            cls._lock = asyncio.Lock()

        async with cls._lock:
            if cls._ws_connection is None or cls._ws_connection.closed:
                import websockets
                full_url = cls._ws_url
                if cls._token:
                    full_url = f"{cls._ws_url}?access_token={cls._token}"
                print(f"[QQ_Reply] Connecting to {full_url[:50]}...")
                cls._ws_connection = await websockets.connect(full_url, compression=None)
                print("[QQ_Reply] Connected!")
            return cls._ws_connection

    @classmethod
    async def send_message(
        cls,
        action: str,
        params: Dict[str, Any],
        timeout: float = 5.0
    ) -> Dict[str, Any]:
        """
        Send a message via the shared connection.

        Args:
            action: OneBot action name (e.g., 'send_private_msg')
            params: Action parameters
            timeout: Response timeout in seconds

        Returns:
            Dict with 'success' and optional 'data' or 'error'
        """
        # Load config if not configured
        if not cls._token:
            cls._load_config()

        ws = await cls.get_connection()
        echo_id = f"qq_reply_{id(params)}"
        payload = json.dumps({'action': action, 'params': params, 'echo': echo_id})

        print(f"[QQ_Reply] Sending: {action}, params: {str(params)[:50]}...")
        await ws.send(payload)

        try:
            resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
            resp_data = json.loads(resp)
            print(f"[QQ_Reply] Received: {resp[:100] if resp else 'None'}")

            if resp_data.get('echo') == echo_id:
                if resp_data.get('status') == 'ok':
                    return {'success': True, 'data': resp_data.get('data')}
                else:
                    return {
                        'success': False,
                        'error': resp_data.get('message') or resp_data.get('wording'),
                        'data': resp_data.get('data')
                    }
        except asyncio.TimeoutError:
            print("[QQ_Reply] Timeout waiting for response (message likely sent)")
        except Exception as e:
            print(f"[QQ_Reply] Response error: {e}")

        # Assume success if no error response
        return {'success': True}

    @classmethod
    async def close(cls):
        """Close the shared connection."""
        if cls._ws_connection and not cls._ws_connection.closed:
            await cls._ws_connection.close()
            cls._ws_connection = None


class QQ_Reply_Operator(IOperator):
    """
    QQ Message Reply Operator

    Sends QQ messages via NapCat WebSocket.
    Uses QQConnectionManager to maintain a shared connection.

    Inputs:
        message: Message content to send
        user_id: Target user ID (for private messages)
        group_id: Target group ID (for group messages)
        message_type: 'private' or 'group'

    Outputs:
        success: Whether the message was sent successfully
        data: Response data from NapCat
        error: Error message if failed
    """

    @property
    def name(self) -> str:
        return "plugin.qq_reply"

    @property
    def description(self) -> str:
        return "Send QQ messages via NapCat WebSocket"

    def get_input_ports(self) -> list:
        return [
            Port(name="message", type="string", description="Message content to send"),
            Port(name="user_id", type="integer", description="Target user ID (private)"),
            Port(name="group_id", type="integer", description="Target group ID (group)"),
            Port(name="message_type", type="string", description="Message type: 'private' or 'group'"),
        ]

    def get_output_ports(self) -> list:
        return [
            Port(name="success", type="boolean", description="Whether message was sent"),
            Port(name="data", type="any", description="Response data from NapCat"),
            Port(name="error", type="string", description="Error message if failed"),
        ]

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: Any
    ) -> Dict[str, Any]:
        message = inputs.get('message', '')
        user_id = inputs.get('user_id')
        group_id = inputs.get('group_id', 0)
        message_type = inputs.get('message_type', 'private')

        if not message:
            return {'success': False, 'data': None, 'error': 'Empty message'}

        # Determine action and params
        action = 'send_private_msg' if message_type == 'private' else 'send_group_msg'
        params: Dict[str, Any] = {'message': str(message)}

        if message_type == 'private':
            params['user_id'] = user_id
        else:
            params['group_id'] = group_id

        # Send message
        try:
            result = await QQConnectionManager.send_message(action, params)
            return {
                'success': result.get('success', False),
                'data': result.get('data'),
                'error': result.get('error')
            }
        except Exception as e:
            print(f"[QQ_Reply] Error: {e}")
            return {'success': False, 'data': None, 'error': str(e)}
