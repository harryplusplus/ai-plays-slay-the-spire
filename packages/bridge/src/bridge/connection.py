from contextlib import suppress

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from bridge.command import ThreadedSender


class ConnectionManager:
    def __init__(self, sender: ThreadedSender) -> None:
        self._websocket: WebSocket | None = None
        self._sender = sender

    async def close(self) -> None:
        websocket = self._websocket
        self._websocket = None

        if websocket is None:
            return

        if websocket.application_state not in {
            WebSocketState.CONNECTING,
            WebSocketState.CONNECTED,
        }:
            return

        with suppress(RuntimeError):
            await websocket.close()

    async def on_connect(self, websocket: WebSocket) -> None:
        await self.close()
        await websocket.accept()
        self._websocket = websocket

        try:
            while True:
                command = await websocket.receive_text()
                await self._sender.send(command)
        except WebSocketDisconnect:
            self._websocket = None

    async def send(self, message: str) -> None:
        if (
            self._websocket is not None
            and self._websocket.application_state == WebSocketState.CONNECTED
        ):
            await self._websocket.send_text(message)
