import asyncio
from contextlib import suppress
from dataclasses import dataclass

from bridge.command_id_service import CommandIdService
from bridge.command_writer import CommandWriter
from bridge.common import Message
from bridge.event_service import EventService
from bridge.models import CommandId, utc_now

EXECUTION_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, kw_only=True)
class Execution:
    future: asyncio.Future[Message]
    command_id: CommandId


class ExecutionService:
    def __init__(
        self,
        command_id_service: CommandIdService,
        command_writer: CommandWriter,
        event_service: EventService,
    ) -> None:
        self._command_id_service = command_id_service
        self._command_writer = command_writer
        self._event_service = event_service
        self._executions: dict[str, Execution] = {}
        self._timeout_task: asyncio.Task[None] | None = None

    async def init(self) -> None:
        self._timeout_task = asyncio.create_task(self._run_timeout())

    async def close(self) -> None:
        if self._timeout_task is not None:
            self._timeout_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._timeout_task

    async def _run_timeout(self) -> None:
        while True:
            await asyncio.sleep(1)
            now = utc_now()
            to_remove: list[str] = []
            for key, execution in self._executions.items():
                elapsed = (now - execution.command_id.updated_at_utc).total_seconds()
                if elapsed > EXECUTION_TIMEOUT_SECONDS:
                    if not execution.future.done():
                        execution.future.set_result(
                            Message(
                                command_id=str(execution.command_id.value),
                                error="Command timed out",
                            )
                        )

                    to_remove.append(key)

            for key in to_remove:
                self._executions.pop(key, None)

    async def execute(self, command: str) -> Message:
        command_id = await self._command_id_service.next()
        key = str(command_id.value)
        if key in self._executions:
            raise RuntimeError(f"Duplicate command_id: {command_id.value}")

        future: asyncio.Future[Message] = asyncio.get_running_loop().create_future()
        self._executions[key] = Execution(future=future, command_id=command_id)
        updated_command = f"--command-id={command_id.value} {command}"

        try:
            self._command_writer.write(updated_command)
            await self._event_service.add("command", updated_command)
        except BaseException:
            self._executions.pop(key, None)
            raise

        return await future

    def receive_message(self, message: Message) -> None:
        if message.command_id is not None:
            execution = self._executions.pop(message.command_id, None)
            if execution is not None and not execution.future.done():
                execution.future.set_result(message)
