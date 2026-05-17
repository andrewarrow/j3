import asyncio

import pytest

from websocketstate import WebSocket, connecting_send_error_message


def test_connecting_send_error_names_allowed_messages() -> None:
    websocket = WebSocket()
    expected = 'Expected message "websocket.accept" or "websocket.close"'

    assert connecting_send_error_message("websocket.send") == expected

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(websocket.send({"type": "websocket.send"}))

    assert str(exc_info.value) == expected
