"""Small WebSocket state fixture derived from Starlette."""

from .websockets import WebSocket, WebSocketState, connecting_send_error_message

__all__ = ["WebSocket", "WebSocketState", "connecting_send_error_message"]
