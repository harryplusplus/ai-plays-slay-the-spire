from typing import Protocol

from typing_extensions import override

from bridge.command import CommandSenderService, CommandSenderServiceImpl
from bridge.connection import ConnectionManagerService, ConnectionManagerServiceImpl
from bridge.message import MessageReceiverService, MessageReceiverServiceImpl


class ServiceRegistry(Protocol):
    async def start(self) -> None: ...
    async def close(self) -> None: ...
    def connection_manager_service(self) -> ConnectionManagerService: ...


class ServiceRegistryImpl(ServiceRegistry):
    def __init__(
        self,
        command_sender_service: CommandSenderService | None = None,
        connection_manager_service: ConnectionManagerService | None = None,
        message_receiver_service: MessageReceiverService | None = None,
    ) -> None:
        self._command_sender_service = (
            command_sender_service
            if command_sender_service is not None
            else CommandSenderServiceImpl()
        )
        self._connection_manager_service = (
            connection_manager_service
            if connection_manager_service is not None
            else ConnectionManagerServiceImpl(
                self._command_sender_service.command_sender(),
            )
        )
        self._message_receiver_service = (
            message_receiver_service
            if message_receiver_service is not None
            else MessageReceiverServiceImpl(
                self._connection_manager_service.message_handler(),
            )
        )

    @override
    async def start(self) -> None:
        self._message_receiver_service.start()
        await self._command_sender_service.command_sender()("ready")

    @override
    async def close(self) -> None:
        await self._connection_manager_service.close()
        self._command_sender_service.close()

    @override
    def connection_manager_service(self) -> ConnectionManagerService:
        return self._connection_manager_service
