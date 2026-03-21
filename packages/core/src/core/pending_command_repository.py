from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from core.models import PendingCommand


class PendingCommandRepository(Protocol):
    async def add(self, command: str) -> int: ...
    async def get_next_pending(self) -> PendingCommand | None: ...
    async def mark_recorded(self, pending_command_id: int) -> None: ...
    async def skip_all_pending(self) -> list[PendingCommand]: ...


class AlchemyPendingCommandRepository(PendingCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @override
    async def add(self, command: str) -> int:
        pending_command = PendingCommand(command=command)
        self._session.add(pending_command)
        await self._session.flush()
        return pending_command.id

    @override
    async def get_next_pending(self) -> PendingCommand | None:
        statement = (
            select(PendingCommand)
            .where(PendingCommand.status == "pending")
            .order_by(PendingCommand.id.asc())
            .limit(1)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    @override
    async def mark_recorded(self, pending_command_id: int) -> None:
        statement = (
            update(PendingCommand)
            .where(PendingCommand.id == pending_command_id)
            .where(PendingCommand.status == "pending")
            .values(status="recorded")
        )
        await self._session.execute(statement)

    @override
    async def skip_all_pending(self) -> list[PendingCommand]:
        statement = (
            select(PendingCommand)
            .where(PendingCommand.status == "pending")
            .order_by(PendingCommand.id.asc())
        )
        result = await self._session.execute(statement)
        pending_commands = list(result.scalars())

        for pending_command in pending_commands:
            pending_command.status = "skipped"

        return pending_commands
