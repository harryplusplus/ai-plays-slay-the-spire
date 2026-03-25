import asyncio
import logging
import threading
from contextlib import suppress
from typing import TextIO

logger = logging.getLogger(__name__)


RawMessage = str | None


def _run(
    input_: TextIO,
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[RawMessage],
) -> None:
    logger.info("Message thread started.")

    while True:
        line = input_.readline()
        if line == "":
            break

        try:
            loop.call_soon_threadsafe(queue.put_nowait, line.rstrip())
        except RuntimeError:
            logger.exception("Failed to put message in queue.")
            break

    with suppress(RuntimeError):
        queue.put_nowait(None)

    logger.info("Message thread closed.")


def start(
    input_: TextIO,
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[RawMessage],
) -> threading.Thread:
    thread = threading.Thread(
        target=_run,
        args=(input_, loop, queue),
        daemon=True,
    )
    thread.start()
    return thread
