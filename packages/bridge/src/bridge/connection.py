import logging
from contextlib import suppress
from typing import Protocol

from fastapi import WebSocket, WebSocketDisconnect
from typing_extensions import override

from bridge import command, message

logger = logging.getLogger(__name__)


class ManagerService(Protocol):
    async def on_websocket(self, websocket: WebSocket) -> None: ...
    async def broadcast(self, message: str) -> None: ...
    async def close(self) -> None: ...
    def message_handler(self) -> message.Handler: ...


class ManagerServiceImpl(ManagerService):
    def __init__(self, command_sender: command.Sender) -> None:
        self._websockets: set[WebSocket] = set()
        self._command_sender = command_sender
        self._closed = False

    @override
    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        websockets = self._websockets.copy()
        self._websockets.clear()

        for websocket in websockets:
            with suppress(WebSocketDisconnect, RuntimeError):
                await websocket.close(1001, "Connection manager is closed.")

    @override
    async def on_websocket(self, websocket: WebSocket) -> None:
        self._check_closed()

        if websocket in self._websockets:
            raise RuntimeError("WebSocket is already connected.")

        await websocket.accept()

        self._websockets.add(websocket)
        try:
            while True:
                try:
                    command = await websocket.receive_text()
                except (WebSocketDisconnect, RuntimeError):
                    break

                await self._command_sender(command)
        finally:
            self._websockets.discard(websocket)

    @override
    async def broadcast(self, message: str) -> None:
        self._check_closed()

        stale_websockets: set[WebSocket] = set()
        try:
            for websocket in self._websockets.copy():
                try:
                    await websocket.send_text(message)
                except (WebSocketDisconnect, RuntimeError):
                    stale_websockets.add(websocket)
        finally:
            for websocket in stale_websockets:
                self._websockets.discard(websocket)

    def _check_closed(self) -> None:
        if self._closed:
            raise RuntimeError("Connection manager is closed.")

    @override
    def message_handler(self) -> message.Handler:
        return self.broadcast
