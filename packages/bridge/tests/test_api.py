from bridge.api import AppFactory
from bridge.connection import Connection, ConnectionManagerService
from bridge.message import MessageHandler
from bridge.service import ServiceRegistry
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typing_extensions import override


class _FakeConnectionManagerService(ConnectionManagerService):
    def __init__(self) -> None:
        self.received_commands: list[str] = []
        self.closed = False

    @override
    async def on_connection(self, connection: Connection) -> None:
        await connection.accept()
        self.received_commands.append(await connection.receive_text())

    @override
    async def broadcast(self, message: str) -> None:
        _ = message

    @override
    async def close(self) -> None:
        self.closed = True

    @override
    def message_handler(self) -> MessageHandler:
        return self.broadcast


class _FakeServiceRegistry(ServiceRegistry):
    def __init__(
        self,
        connection_manager_service: ConnectionManagerService,
    ) -> None:
        self._connection_manager_service = connection_manager_service
        self.started = False
        self.closed = False

    @override
    async def start(self) -> None:
        self.started = True

    @override
    async def close(self) -> None:
        self.closed = True

    @override
    def connection_manager_service(self) -> ConnectionManagerService:
        return self._connection_manager_service


def test_test_client_runs_registry_lifecycle() -> None:
    service_registry = _FakeServiceRegistry(_FakeConnectionManagerService())
    app = AppFactory(service_registry)()

    with TestClient(app):
        assert service_registry.started is True
        assert app.state.service_registry is service_registry

    assert service_registry.closed is True


def test_websocket_route_forwards_commands_to_connection_manager() -> None:
    connection_manager_service = _FakeConnectionManagerService()
    app = AppFactory(_FakeServiceRegistry(connection_manager_service))()

    with (
        TestClient(app) as client,
        client.websocket_connect("/ws") as websocket,
    ):
        websocket.send_text("play")

    assert connection_manager_service.received_commands == ["play"]


def test_app_factory_uses_default_registry_when_not_provided() -> None:
    app = AppFactory()()

    assert isinstance(app, FastAPI)
    assert app.router.routes
