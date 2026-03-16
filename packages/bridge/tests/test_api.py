from dataclasses import dataclass

from bridge import api, connection, message, service
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from typing_extensions import override


class _FakeConnectionManager(connection.ManagerService):
    def __init__(self) -> None:
        self.received_commands: list[str] = []
        self.closed = False

    @override
    async def on_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.received_commands.append(await websocket.receive_text())

    @override
    async def broadcast(self, message: str) -> None:
        _ = message

    @override
    async def close(self) -> None:
        self.closed = True

    @override
    def message_handler(self) -> message.Handler:
        return self.broadcast


@dataclass
class _FakeRegistry(service.Registry):
    connection_manager_service: connection.ManagerService
    started: bool = False
    closed: bool = False

    @override
    async def start(self) -> None:
        self.started = True

    @override
    async def close(self) -> None:
        self.closed = True

    @override
    def connection_manager(self) -> connection.ManagerService:
        return self.connection_manager_service


def test_test_client_runs_registry_lifecycle() -> None:
    registry = _FakeRegistry(_FakeConnectionManager())
    app = api.create_app(registry=registry)

    with TestClient(app):
        assert registry.started is True
        assert app.state.registry is registry

    assert registry.closed is True


def test_websocket_route_forwards_commands_to_connection_manager() -> None:
    manager = _FakeConnectionManager()
    app = api.create_app(registry=_FakeRegistry(manager))

    with (
        TestClient(app) as client,
        client.websocket_connect("/ws") as websocket,
    ):
        websocket.send_text("play")

    assert manager.received_commands == ["play"]


def test_module_level_app_uses_create_app() -> None:
    assert isinstance(api.app, FastAPI)
    assert api.app.router.routes
