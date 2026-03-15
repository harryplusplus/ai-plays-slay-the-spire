import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol, TextIO

from typing_extensions import override

logger = logging.getLogger(__name__)


class Writer:
    def __init__(self, out: TextIO | None = None) -> None:
        self._out: TextIO = out if out is not None else sys.stdout

    def __call__(self, command: str) -> None:
        self._out.write(f"{command}\n")
        self._out.flush()


class Sender(Protocol):
    async def __call__(self, command: str) -> None: ...


class SenderService(Protocol):
    def sender(self) -> Sender: ...

    def close(self) -> None: ...


class ThreadedSenderService(SenderService):
    def __init__(self, writer: Writer | None = None) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._writer = writer if writer is not None else Writer()

    @override
    def close(self) -> None:
        logger.info("ThreadedSenderService closing...")
        self._executor.shutdown()
        logger.info("ThreadedSenderService closed.")

    async def _send(self, command: str) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self._writer, command)

    @override
    def sender(self) -> Sender:
        return self._send
