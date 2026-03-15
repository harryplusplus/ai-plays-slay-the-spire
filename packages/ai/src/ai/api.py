import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Protocol, cast

from typing_extensions import override
from websockets.asyncio.client import connect as ws_connect

BRIDGE_WS_URL = "ws://localhost:8000/ws"


class WebSocketClient(Protocol):
    async def send(self, message: str) -> None: ...

    async def recv(self) -> str | bytes: ...


class Session(Protocol):
    async def communicate(self, command: str) -> dict[str, Any]: ...


Connector = Callable[[str], AbstractAsyncContextManager[WebSocketClient]]


class WebSocketSession(Session):
    def __init__(self, websocket: WebSocketClient) -> None:
        self._websocket = websocket

    @override
    async def communicate(self, command: str) -> dict[str, Any]:
        await self._websocket.send(command)
        response = await self._websocket.recv()

        if not isinstance(response, str):
            raise TypeError("Expected text message from bridge.")

        data = json.loads(response)
        if not isinstance(data, dict):
            raise TypeError("Expected JSON object from bridge.")

        return cast("dict[str, Any]", data)


@asynccontextmanager
async def connect(
    *,
    url: str = BRIDGE_WS_URL,
    connector: Connector = ws_connect,
) -> AsyncIterator[Session]:
    async with connector(url) as websocket:
        yield WebSocketSession(websocket)
