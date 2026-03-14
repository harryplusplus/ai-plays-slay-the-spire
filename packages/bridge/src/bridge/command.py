import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TextIO

logger = logging.getLogger(__name__)


class Sender:
    def __init__(self, out: TextIO | None = None) -> None:
        self._out: TextIO = out if out is not None else sys.stdout

    def send(self, command: str) -> None:
        self._out.write(f"{command}\n")
        self._out.flush()


class ThreadedSender:
    def __init__(self, sender: Sender | None = None) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._sender = sender if sender is not None else Sender()

    def close(self) -> None:
        logger.info("ThreadedSender shutting down...")
        self._executor.shutdown()
        logger.info("ThreadedSender shut down.")

    async def send(self, command: str) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self._sender.send, command)
