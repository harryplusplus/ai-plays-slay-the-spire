import asyncio
import logging
from contextlib import suppress

from bridge.common import Message
from bridge.event_service import EventServiceProtocol
from bridge.execution_service import ExecutionServiceProtocol
from bridge.message_thread import RawMessage

logger = logging.getLogger(__name__)


class MessageService:
    def __init__(
        self,
        queue: asyncio.Queue[RawMessage],
        execution_service: ExecutionServiceProtocol,
        event_service: EventServiceProtocol,
    ) -> None:
        self._queue = queue
        self._execution_service = execution_service
        self._event_service = event_service
        self._task: asyncio.Task[None] | None = None

    async def init(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        while True:
            raw = await self._queue.get()
            if raw is None:
                break

            await self._event_service.add("message", raw)

            try:
                parsed = Message.model_validate_json(raw)
            except Exception:
                logger.exception("Failed to parse message: %s", raw)
                continue

            self._execution_service.receive_message(parsed)
