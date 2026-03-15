import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest
from bridge import api, command, connection, message
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typing_extensions import override

HTTP_OK = 200


class _FakeSenderService(command.SenderService):
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.closed = False

    async def _send(self, command: str) -> None:
        self.commands.append(command)

    @override
    def sender(self) -> command.Sender:
        return self._send

    @override
    def close(self) -> None:
        self.closed = True


class _FakeReceiverService(message.ReceiverService):
    def __init__(self, handler: message.Handler) -> None:
        self.handler = handler
        self.started = False

    @override
    def start(self) -> None:
        self.started = True


@dataclass
class _Resources:
    command_sender: _FakeSenderService | None = None
    message_receiver: _FakeReceiverService | None = None


def _create_test_app() -> tuple[FastAPI, _Resources]:
    resources = _Resources()

    def command_sender_factory() -> _FakeSenderService:
        resources.command_sender = _FakeSenderService()
        return resources.command_sender

    def message_receiver_factory(handler: message.Handler) -> _FakeReceiverService:
        resources.message_receiver = _FakeReceiverService(handler)
        return resources.message_receiver

    app = api.create_app(
        factories=api.RuntimeFactories(
            command_sender=command_sender_factory,
            message_receiver=message_receiver_factory,
        ),
    )
    return app, resources


def test_get_connection_manager_reads_app_state() -> None:
    manager = object()
    websocket = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(connection_manager=manager),
        ),
    )

    assert api.get_connection_manager(cast("Any", websocket)) is manager


def test_health_route_runs_lifespan_and_closes_resources() -> None:
    app, resources = _create_test_app()

    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == HTTP_OK
        assert response.json() == "ok"
        assert resources.command_sender is not None
        assert resources.message_receiver is not None
        assert resources.command_sender.commands == ["ready"]
        assert resources.message_receiver.started is True

    assert resources.command_sender is not None
    assert resources.command_sender.closed is True

    with pytest.raises(RuntimeError, match=r"Connection manager is closed\."):
        asyncio.run(app.state.connection_manager.broadcast("after"))


def test_websocket_route_forwards_commands_to_sender() -> None:
    app, resources = _create_test_app()

    with (
        TestClient(app) as client,
        client.websocket_connect("/ws") as websocket,
    ):
        websocket.send_text("play")

    assert resources.command_sender is not None
    assert resources.command_sender.commands == ["ready", "play"]


def test_module_level_app_uses_create_app() -> None:
    assert isinstance(api.app, FastAPI)
    assert api.app.router.routes


def test_create_app_uses_custom_connection_manager_factory() -> None:
    created_managers: list[connection.Manager] = []

    def command_sender_factory() -> _FakeSenderService:
        return _FakeSenderService()

    def message_receiver_factory(handler: message.Handler) -> _FakeReceiverService:
        return _FakeReceiverService(handler)

    def connection_manager_factory(
        command_sender: command.Sender,
    ) -> connection.Manager:
        manager = connection.Manager(command_sender)
        created_managers.append(manager)
        return manager

    app = api.create_app(
        factories=api.RuntimeFactories(
            command_sender=command_sender_factory,
            connection_manager=connection_manager_factory,
            message_receiver=message_receiver_factory,
        ),
    )

    with TestClient(app):
        pass

    assert len(created_managers) == 1
