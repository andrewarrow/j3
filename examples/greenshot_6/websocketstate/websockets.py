"""Small WebSocket state helpers derived from Starlette."""

from __future__ import annotations

from enum import Enum


class WebSocketState(Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


def connecting_send_error_message(message_type: str) -> str:
    return 'Expected message "websocket.connect"'


class WebSocket:
    def __init__(self) -> None:
        self.application_state = WebSocketState.CONNECTING

    async def send(self, message: dict[str, str]) -> None:
        if self.application_state == WebSocketState.CONNECTING:
            message_type = message["type"]
            if message_type not in {"websocket.accept", "websocket.close"}:
                raise RuntimeError(connecting_send_error_message(message_type))
            if message_type == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED
            else:
                self.application_state = WebSocketState.CONNECTED
            return

        if self.application_state == WebSocketState.DISCONNECTED:
            raise RuntimeError("Cannot call send after close.")
