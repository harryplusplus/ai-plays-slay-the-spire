import asyncio
import logging

from core.paths import DB_SQLITE

from bridge import message_thread
from bridge.command_id_service import CommandIdService
from bridge.command_writer import CommandWriter
from bridge.db import Db
from bridge.event_service import EventService
from bridge.execution_service import ExecutionService
from bridge.message_service import MessageService

logger = logging.getLogger(__name__)


class Container:
    def __init__(  # noqa: PLR0913
        self,
        message_queue: asyncio.Queue[message_thread.RawMessage],
        db: Db | None = None,
        command_writer: CommandWriter | None = None,
        execution_service: ExecutionService | None = None,
        message_service: MessageService | None = None,
        command_id_service: CommandIdService | None = None,
        event_service: EventService | None = None,
    ) -> None:
        self._message_queue = message_queue
        self._db = db if db is not None else Db(DB_SQLITE)
        self._command_writer = (
            command_writer if command_writer is not None else CommandWriter()
        )
        self._command_id_service = (
            command_id_service
            if command_id_service is not None
            else CommandIdService(self._db)
        )
        self.event_service = (
            event_service if event_service is not None else EventService(self._db)
        )
        self.execution_service = (
            execution_service
            if execution_service is not None
            else ExecutionService(
                self._command_id_service,
                self._command_writer,
                self.event_service,
            )
        )
        self._message_service = (
            message_service
            if message_service is not None
            else MessageService(
                self._message_queue, self.execution_service, self.event_service
            )
        )

    async def init(self) -> None:
        await self._db.init()
        await self._message_service.init()
        await self.execution_service.init()
        await self.execution_service.execute("ready")

    async def close(self) -> None:
        await self.execution_service.close()
        await self._message_service.close()
        await self._db.close()
