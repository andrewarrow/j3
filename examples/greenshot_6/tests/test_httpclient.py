import asyncio

import pytest

from httpclient import AsyncClient, Request, SyncByteStream


def test_async_client_sync_request_error_message_uses_a() -> None:
    client = AsyncClient()

    with pytest.raises(
        RuntimeError,
        match="Attempted to send a sync request with an AsyncClient instance.",
    ):
        asyncio.run(client.send(Request(SyncByteStream())))
