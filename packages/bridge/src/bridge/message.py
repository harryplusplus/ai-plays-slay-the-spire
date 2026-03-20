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


def process_next(
    input_stream: TextIO,
    queue: ToAsyncQueue,
) -> bool:
    line = input_stream.readline()
    if line == "":
        return False

    try:
        queue.put_nowait(line.rstrip())
    except ClosedError:
        return False

    return True


def run(
    input_stream: TextIO,
    queue: ToAsyncQueue,
) -> None:
    logger.info("Message thread started.")

    while process_next(input_stream, queue):
        pass

    with suppress(ClosedError):
        queue.put_nowait(None)

    logger.info("Message thread closed.")


def start_thread(input_stream: TextIO, queue: ToAsyncQueue) -> threading.Thread:
    thread = threading.Thread(
        target=run,
        args=(input_stream, queue),
        daemon=True,
    )
    thread.start()
    return thread
