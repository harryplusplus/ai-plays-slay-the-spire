import pytest
from bridge.command import CommandSender, CommandSenderService
from bridge.connection import ConnectionManagerService
from bridge.message import MessageHandler, MessageReceiverService
from bridge.service import ServiceRegistryImpl
from fastapi import WebSocket
from typing_extensions import override


class _FakeCommandSenderService(CommandSenderService):
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.closed = False

    async def _send(self, command: str) -> None:
        self.commands.append(command)

    @override
    def command_sender(self) -> CommandSender:
        return self._send

    @override
    def close(self) -> None:
        self.closed = True


class _FakeConnectionManagerService(ConnectionManagerService):
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
    def message_handler(self) -> MessageHandler:
        return self.broadcast


class _FakeMessageReceiverService(MessageReceiverService):
    def __init__(self) -> None:
        self.started = False

    @override
    def start(self) -> None:
        self.started = True


@pytest.mark.anyio
async def test_registry_impl_starts_receiver_and_sends_ready() -> None:
    command_sender_service = _FakeCommandSenderService()
    connection_manager_service = _FakeConnectionManagerService()
    message_receiver_service = _FakeMessageReceiverService()
    service_registry = ServiceRegistryImpl(
        command_sender_service=command_sender_service,
        connection_manager_service=connection_manager_service,
        message_receiver_service=message_receiver_service,
    )

    await service_registry.start()

    assert message_receiver_service.started is True
    assert command_sender_service.commands == ["ready"]


@pytest.mark.anyio
async def test_registry_impl_closes_connection_manager_and_sender() -> None:
    command_sender_service = _FakeCommandSenderService()
    connection_manager_service = _FakeConnectionManagerService()
    service_registry = ServiceRegistryImpl(
        command_sender_service=command_sender_service,
        connection_manager_service=connection_manager_service,
        message_receiver_service=_FakeMessageReceiverService(),
    )

    await service_registry.close()

    assert connection_manager_service.closed is True
    assert command_sender_service.closed is True


def test_registry_impl_returns_connection_manager() -> None:
    connection_manager_service = _FakeConnectionManagerService()
    service_registry = ServiceRegistryImpl(
        command_sender_service=_FakeCommandSenderService(),
        connection_manager_service=connection_manager_service,
        message_receiver_service=_FakeMessageReceiverService(),
    )

    assert service_registry.connection_manager_service() is connection_manager_service
