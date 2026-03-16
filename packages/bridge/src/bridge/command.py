import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol, TextIO

from typing_extensions import override

logger = logging.getLogger(__name__)


class CommandWriter:
    def __init__(self, out: TextIO | None = None) -> None:
        self._out: TextIO = out if out is not None else sys.stdout

    def __call__(self, command: str) -> None:
        self._out.write(f"{command}\n")
        self._out.flush()


class CommandSender(Protocol):
    async def __call__(self, command: str) -> None: ...


class CommandSenderService(Protocol):
    def close(self) -> None: ...
    def command_sender(self) -> CommandSender: ...


class CommandSenderServiceImpl(CommandSenderService):
    def __init__(self, command_writer: CommandWriter | None = None) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._command_writer = (
            command_writer if command_writer is not None else CommandWriter()
        )
        self._logger = logger.getChild("CommandSenderServiceImpl")

    @override
    def close(self) -> None:
        self._logger.info("Closing...")
        self._executor.shutdown()
        self._logger.info("Closed.")

    async def _send(self, command: str) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self._command_writer, command)

    @override
    def command_sender(self) -> CommandSender:
        return self._send
