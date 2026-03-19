import asyncio
import logging
import threading
from collections.abc import Callable
from contextlib import suppress
from typing import Protocol, TextIO

logger = logging.getLogger(__name__)


MessageQueue = asyncio.Queue[str | None]


class MessageLoop(Protocol):
    def call_soon_threadsafe(
        self,
        callback: Callable[..., object],
        *args: object,
    ) -> object: ...


def forward_next_message(
    input_stream: TextIO,
    loop: MessageLoop,
    queue: MessageQueue,
) -> bool:
    line = input_stream.readline()
    if line == "":
        return False

    try:
        loop.call_soon_threadsafe(queue.put_nowait, line.rstrip())
    except RuntimeError:
        return False

    return True


def run_message_thread(
    input_stream: TextIO,
    loop: MessageLoop,
    queue: MessageQueue,
) -> None:
    logger.info("Message thread started.")

    while forward_next_message(input_stream, loop, queue):
        pass

    with suppress(RuntimeError):
        loop.call_soon_threadsafe(queue.put_nowait, None)

    logger.info("Message thread closed.")


def start_message_thread(
    input_stream: TextIO,
    loop: MessageLoop,
    queue: MessageQueue,
) -> threading.Thread:
    thread = threading.Thread(
        target=run_message_thread,
        args=(input_stream, loop, queue),
        daemon=True,
    )
    thread.start()
    return thread
