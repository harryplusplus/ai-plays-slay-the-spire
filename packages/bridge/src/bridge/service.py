from typing import Protocol

from typing_extensions import override

from bridge import command, connection, message


class Registry(Protocol):
    async def start(self) -> None: ...
    async def close(self) -> None: ...
    def connection_manager(self) -> connection.ManagerService: ...


class RegistryImpl(Registry):
    def __init__(
        self,
        command_sender: command.SenderService | None = None,
        connection_manager: connection.ManagerService | None = None,
        message_receiver: message.ReceiverService | None = None,
    ) -> None:
        self._command_sender = (
            command_sender
            if command_sender is not None
            else command.SenderServiceImpl()
        )
        self._connection_manager = (
            connection_manager
            if connection_manager is not None
            else connection.ManagerServiceImpl(self._command_sender.sender())
        )
        self._message_receiver = (
            message_receiver
            if message_receiver is not None
            else message.ReceiverServiceImpl(
                self._connection_manager.message_handler(),
            )
        )

    @override
    async def start(self) -> None:
        self._message_receiver.start()
        await self._command_sender.sender()("ready")

    @override
    async def close(self) -> None:
        await self._connection_manager.close()
        self._command_sender.close()

    @override
    def connection_manager(self) -> connection.ManagerService:
        return self._connection_manager
