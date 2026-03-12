import asyncio
import logging
import sys
import threading

from bridge.common import Message, MessageQueue

logger = logging.getLogger(__name__)


def _main(loop: asyncio.AbstractEventLoop, message_queue: MessageQueue) -> None:
    logger.info("Started.")

    for message_id, line in enumerate(sys.stdin):
        message = line.rstrip()
        loop.call_soon_threadsafe(
            message_queue.put_nowait,
            Message(id=message_id, message=message),
        )

    logger.info("Exited.")


def create_thread(
    loop: asyncio.AbstractEventLoop,
    message_queue: MessageQueue,
) -> threading.Thread:
    return threading.Thread(
        name="message_thread",
        target=_main,
        args=(loop, message_queue),
    )
