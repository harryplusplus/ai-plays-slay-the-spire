import asyncio
import logging
import threading
from contextlib import suppress
from typing import TextIO

logger = logging.getLogger(__name__)


MessageQueue = asyncio.Queue[str | None]


def forward_next_message(
    input_stream: TextIO,
    loop: asyncio.AbstractEventLoop,
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
    loop: asyncio.AbstractEventLoop,
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
    loop: asyncio.AbstractEventLoop,
    queue: MessageQueue,
) -> threading.Thread:
    thread = threading.Thread(
        target=run_message_thread,
        args=(input_stream, loop, queue),
        daemon=True,
    )
    thread.start()
    return thread
