import asyncio
import logging
import threading
from contextlib import suppress
from typing import TextIO

logger = logging.getLogger(__name__)


Queue = asyncio.Queue[str | None]


class ClosedError(Exception):
    pass


class ToAsyncQueue:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        queue: Queue,
    ) -> None:
        self._loop = loop
        self._queue = queue

    def put_nowait(self, item: str | None) -> None:
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, item)
        except RuntimeError as e:
            raise ClosedError("Message queue is closed.") from e


def _process_next(
    input_: TextIO,
    queue: ToAsyncQueue,
) -> bool:
    line = input_.readline()
    if line == "":
        return False

    try:
        queue.put_nowait(line.rstrip())
    except ClosedError:
        return False

    return True


def _run(
    input_: TextIO,
    queue: ToAsyncQueue,
) -> None:
    logger.info("Message thread started.")

    while _process_next(input_, queue):
        pass

    with suppress(ClosedError):
        queue.put_nowait(None)

    logger.info("Message thread closed.")


def start_thread(input_: TextIO, queue: ToAsyncQueue) -> threading.Thread:
    thread = threading.Thread(
        target=_run,
        args=(input_, queue),
        daemon=True,
    )
    thread.start()
    return thread
