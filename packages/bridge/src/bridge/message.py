import asyncio
import concurrent.futures
import logging
import sys
import threading
from typing import Protocol, TextIO

from typing_extensions import override

logger = logging.getLogger(__name__)


class Reader:
    def __init__(self, in_: TextIO | None = None) -> None:
        self._in: TextIO = in_ if in_ is not None else sys.stdin

    def __call__(self) -> str:
        line = self._in.readline()
        if line == "":
            raise EOFError("message.Reader reached EOF.")
        return line.rstrip()


def _on_done(future: concurrent.futures.Future[None]) -> None:
    try:
        future.result()
    except Exception:
        logger.exception("Error sending message to connection.")


class Handler(Protocol):
    async def __call__(self, message: str) -> None: ...


class ReceiverService(Protocol):
    def start(self) -> None: ...


class ThreadedReceiverService(ReceiverService):
    def __init__(
        self,
        handler: Handler,
        reader: Reader | None = None,
    ) -> None:
        self._handler = handler
        self._reader = reader if reader is not None else Reader()
        self._thread: threading.Thread | None = None

    @override
    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._thread = threading.Thread(
            target=self._run,
            args=(loop,),
            daemon=True,
        )
        self._thread.start()

    def _run(self, loop: asyncio.AbstractEventLoop) -> None:
        while True:
            try:
                message = self._reader()
            except EOFError:
                logger.info(
                    "Stopping ThreadedReceiverService loop due to EOFError.",
                )
                break

            future = asyncio.run_coroutine_threadsafe(
                self._handler(message),
                loop,
            )
            future.add_done_callback(_on_done)
