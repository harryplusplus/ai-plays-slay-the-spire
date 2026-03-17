from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import ParamSpec, Protocol, TypeVar

from fastapi import WebSocketDisconnect
from typing_extensions import override

from bridge.command import CommandSender
from bridge.message import MessageHandler

P = ParamSpec("P")
R = TypeVar("R")


class BridgeConnectionError(Exception):
    pass


class Connection(Protocol):
    async def accept(self) -> None: ...
    async def receive_text(self) -> str: ...
    async def send_text(self, message: str) -> None: ...
    async def close(self, code: int, reason: str) -> None: ...


class ConnectionManagerService(Protocol):
    async def on_connection(self, connection: Connection) -> None: ...
    async def broadcast(self, message: str) -> None: ...
    async def close(self) -> None: ...
    def message_handler(self) -> MessageHandler: ...


class WebSocketConnection(Connection):
    def __init__(self, websocket: Connection) -> None:
        self._websocket = websocket

    @override
    async def accept(self) -> None:
        await self._call(self._websocket.accept)

    @override
    async def receive_text(self) -> str:
        return await self._call(self._websocket.receive_text)

    @override
    async def send_text(self, message: str) -> None:
        await self._call(self._websocket.send_text, message)

    @override
    async def close(self, code: int, reason: str) -> None:
        await self._call(self._websocket.close, code, reason)

    async def _call(
        self,
        operation: Callable[P, Awaitable[R]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        try:
            return await operation(*args, **kwargs)
        except (WebSocketDisconnect, RuntimeError) as e:
            raise BridgeConnectionError from e


class ConnectionManagerServiceImpl(ConnectionManagerService):
    def __init__(self, command_sender: CommandSender) -> None:
        self._connections: set[Connection] = set()
        self._command_sender = command_sender
        self._closed = False

    @override
    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        connections = self._connections.copy()
        self._connections.clear()

        for connection in connections:
            with suppress(BridgeConnectionError):
                await connection.close(1001, "Connection manager is closed.")

    @override
    async def on_connection(self, connection: Connection) -> None:
        self._check_closed()

        if connection in self._connections:
            raise RuntimeError("Connection is already connected.")

        await connection.accept()

        self._connections.add(connection)
        try:
            while True:
                try:
                    command = await connection.receive_text()
                except BridgeConnectionError:
                    break

                await self._command_sender(command)
        finally:
            self._connections.discard(connection)

    @override
    async def broadcast(self, message: str) -> None:
        self._check_closed()

        stale_connections: set[Connection] = set()
        try:
            for connection in self._connections.copy():
                try:
                    await connection.send_text(message)
                except BridgeConnectionError:
                    stale_connections.add(connection)
        finally:
            for connection in stale_connections:
                self._connections.discard(connection)

    def _check_closed(self) -> None:
        if self._closed:
            raise RuntimeError("Connection manager is closed.")

    @override
    def message_handler(self) -> MessageHandler:
        return self.broadcast
