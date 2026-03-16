import pytest
from bridge import command, connection, message, service
from fastapi import WebSocket
from typing_extensions import override


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


class _FakeConnectionManager(connection.ManagerService):
    def __init__(self) -> None:
        self.closed = False

    @override
    async def on_websocket(self, websocket: WebSocket) -> None:
        _ = websocket

    @override
    async def broadcast(self, message: str) -> None:
        _ = message

    @override
    async def close(self) -> None:
        self.closed = True

    @override
    def message_handler(self) -> message.Handler:
        return self.broadcast


class _FakeReceiverService(message.ReceiverService):
    def __init__(self) -> None:
        self.started = False

    @override
    def start(self) -> None:
        self.started = True


@pytest.mark.anyio
async def test_registry_impl_starts_receiver_and_sends_ready() -> None:
    sender = _FakeSenderService()
    manager = _FakeConnectionManager()
    receiver = _FakeReceiverService()
    registry = service.RegistryImpl(
        command_sender=sender,
        connection_manager=manager,
        message_receiver=receiver,
    )

    await registry.start()

    assert receiver.started is True
    assert sender.commands == ["ready"]


@pytest.mark.anyio
async def test_registry_impl_closes_connection_manager_and_sender() -> None:
    sender = _FakeSenderService()
    manager = _FakeConnectionManager()
    registry = service.RegistryImpl(
        command_sender=sender,
        connection_manager=manager,
        message_receiver=_FakeReceiverService(),
    )

    await registry.close()

    assert manager.closed is True
    assert sender.closed is True


def test_registry_impl_returns_connection_manager() -> None:
    manager = _FakeConnectionManager()
    registry = service.RegistryImpl(
        command_sender=_FakeSenderService(),
        connection_manager=manager,
        message_receiver=_FakeReceiverService(),
    )

    assert registry.connection_manager() is manager
