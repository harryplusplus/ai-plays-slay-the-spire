import asyncio
import logging
import sys
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
        self._message_task: asyncio.Task[None] | None = None
        self._message_queue = asyncio.Queue[Message]()
        self._message_id = 0

        self._command_transport: asyncio.WriteTransport | None = None
        self._command_task: asyncio.Task[None] | None = None
        self._command_queue = asyncio.Queue[Command]()
        self._command_id = 0

        self.executing = False
        self.lock = asyncio.Lock()

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._message_transport, _ = await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(self._message_reader),
            sys.stdin.buffer,
        )
        self._message_task = asyncio.create_task(self._message_loop())

        self._command_transport, _ = await loop.connect_write_pipe(
            asyncio.Protocol,
            sys.stdout.buffer,
        )
        self._command_task = asyncio.create_task(self._command_loop())

    async def close(self) -> None:
        self._closed = True

        for task in (self._message_task, self._command_task):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

        if self._message_transport is not None:
            self._message_transport.close()

        if self._command_transport is not None:
            self._command_transport.close()

        self._fail_pending_commands(RuntimeError("Bridge is closed."))

    async def execute(self, command: str) -> str:
        if self._closed:
            raise RuntimeError("Bridge is closed.")

        async with self.lock:
            if self.executing:
                raise RuntimeError("Command is already executing.")
            self.executing = True

        try:
            future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            command_id = self._command_id
            self._command_id += 1

            await self._command_queue.put(
                Command(id=command_id, command=command, future=future),
            )

            return await future
        finally:
            async with self.lock:
                self.executing = False

    async def _message_loop(self) -> None:
        while True:
            raw = await self._message_reader.readline()
            if raw == b"":
                self._closed = True
                self._server.should_exit = True
                return

            message = raw.rstrip(b"\n").decode()
            message_id = self._message_id
            self._message_id += 1

            await self._message_queue.put(Message(id=message_id, message=message))

    async def _command_loop(self) -> None:
        while True:
            command = await self._command_queue.get()
            if command.future.cancelled():
                continue

            try:
                stale_messages = self._drain_stale_messages()
                self._write_command(command.command)
                message = await self._message_queue.get()

                logger.info(
                    "\nCommand: %s,\nMessage: %s\nStale messages: %s",
                    (command.id, command.command),
                    (message.id, message.message),
                    [(m.id, m.message) for m in stale_messages],
                )

                if not command.future.done():
                    command.future.set_result(message.message)
            except Exception as e:
                if not command.future.done():
                    command.future.set_exception(e)

                raise

    def _write_command(self, command: str) -> None:
        if self._command_transport is None:
            raise RuntimeError("Command transport is not initialized.")

        self._command_transport.write(f"{command}\n".encode())

    def _drain_stale_messages(self) -> list[Message]:
        stale_messages: list[Message] = []
        while True:
            try:
                message = self._message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            stale_messages.append(message)

        return stale_messages

    def _fail_pending_commands(self, e: Exception) -> None:
        while True:
            try:
                command = self._command_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            if not command.future.done():
                command.future.set_exception(e)
