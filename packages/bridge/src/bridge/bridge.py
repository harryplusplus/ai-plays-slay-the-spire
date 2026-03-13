import asyncio
import logging
import sys
from collections import deque
from contextlib import suppress
from dataclasses import dataclass

import uvicorn

logger = logging.getLogger(__name__)


@dataclass(kw_only=True, slots=True)
class Command:
    id: int
    command: str
    future: asyncio.Future[str]


@dataclass(kw_only=True, slots=True)
class Message:
    id: int
    message: str


class Bridge:
    def __init__(self, server: uvicorn.Server) -> None:
        self._closed = False
        self._server = server

        self._message_reader = asyncio.StreamReader()
        self._message_transport: asyncio.ReadTransport | None = None
        self._message_id = 0

        self._command_queue = asyncio.Queue[Command]()
        self._command_transport: asyncio.WriteTransport | None = None
        self._command_id = 0

        self._loop_task: asyncio.Task[None] | None = None

        self._executing = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        self._message_transport, _ = await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(self._message_reader),
            sys.stdin.buffer,
        )
        self._command_transport, _ = await loop.connect_write_pipe(
            asyncio.Protocol,
            sys.stdout.buffer,
        )
        self._loop_task = asyncio.create_task(self._loop())

    async def close(self) -> None:
        self._closed = True

        if self._loop_task is not None:
            self._loop_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._loop_task

        if self._message_transport is not None:
            self._message_transport.close()

        if self._command_transport is not None:
            self._command_transport.close()

        self._fail_pending_commands(self._create_eof_error())

    async def execute(self, command: str) -> str:
        if self._closed:
            raise RuntimeError("Bridge is closed.")

        async with self._lock:
            if self._executing:
                raise RuntimeError("Command is already executing.")
            self._executing = True

        try:
            future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            command_id = self._command_id
            self._command_id += 1

            await self._command_queue.put(
                Command(id=command_id, command=command, future=future),
            )

            return await future
        finally:
            async with self._lock:
                self._executing = False

    async def _loop(self) -> None:
        pending_messages = deque[Message]()
        current_command: Command | None = None
        message_task: asyncio.Task[bytes] | None = None
        command_task: asyncio.Task[Command] | None = None

        try:
            message_task = self._create_message_task()
            command_task = self._create_command_task()

            while True:
                done, _ = await asyncio.wait(
                    {message_task, command_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                while message_task in done:
                    raw = message_task.result()
                    if raw == b"":
                        return

                    pending_messages.append(self._create_message(raw))
                    message_task = self._create_message_task()
                    if message_task.done():
                        done.add(message_task)
                    else:
                        break

                if current_command is None and command_task in done:
                    current_command = command_task.result()
                    command_task = self._create_command_task()

                    stale_messages: list[Message] = []
                    while pending_messages:
                        stale_messages.append(pending_messages.popleft())
                    if stale_messages:
                        logger.warning(
                            "Command %s, Stale messages: %s",
                            (current_command.id, current_command.command),
                            [(m.id, m.message) for m in stale_messages],
                        )

                    self._write_command(current_command.command)

                if current_command is not None and pending_messages:
                    message = pending_messages.popleft()

                    if not current_command.future.done():
                        current_command.future.set_result(message.message)

                    logger.info(
                        "Command %s, Message %s",
                        (current_command.id, current_command.command),
                        (message.id, message.message),
                    )

                    current_command = None
        finally:
            self._closed = True
            self._server.should_exit = True

            if current_command is not None and not current_command.future.done():
                current_command.future.set_exception(
                    self._create_eof_error(),
                )

            for task in (message_task, command_task):
                if task is not None:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

    def _write_command(self, command: str) -> None:
        if self._command_transport is None:
            raise RuntimeError("Command transport is not initialized.")

        self._command_transport.write(f"{command}\n".encode())

    def _fail_pending_commands(self, e: Exception) -> None:
        while True:
            try:
                command = self._command_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            if not command.future.done():
                command.future.set_exception(e)

    def _create_message_task(self) -> asyncio.Task[bytes]:
        return asyncio.create_task(self._message_reader.readline())

    def _create_command_task(self) -> asyncio.Task[Command]:
        return asyncio.create_task(self._command_queue.get())

    def _create_message(self, raw: bytes) -> Message:
        message = raw.rstrip(b"\n").decode()
        message_id = self._message_id
        self._message_id += 1
        return Message(id=message_id, message=message)

    def _create_eof_error(self) -> EOFError:
        return EOFError("CommunicationMod closed stdin.")
