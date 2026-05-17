"""Small async client helpers derived from HTTPX."""

from __future__ import annotations

from dataclasses import dataclass


class SyncByteStream:
    pass


class AsyncByteStream:
    pass


@dataclass
class Request:
    stream: object


class AsyncClient:
    async def send(self, request: Request) -> str:
        if not isinstance(request.stream, AsyncByteStream):
            raise RuntimeError(
                "Attempted to send an sync request with an AsyncClient instance."
            )

        return "sent"


def stream_read_docline() -> str:
    return "making request.text and response.content available."
