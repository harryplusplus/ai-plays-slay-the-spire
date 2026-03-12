import asyncio
import logging
import sys

from bridge import api, log
from bridge.common import Message, MessageQueue

logger = logging.getLogger(__name__)


def main() -> None:
    log.init()
    logger.info("Started.")

    loop = asyncio.new_event_loop()
    message_queue = MessageQueue()

    server, api_thread = api.create_thread(
        loop,
        message_queue,
    )

    api_thread.start()

    for message_id, line in enumerate(sys.stdin):
        message = line.rstrip()
        loop.call_soon_threadsafe(
            message_queue.put_nowait,
            Message(id=message_id, message=message),
        )

    server.should_exit = True
    api_thread.join()

    logger.info("Exited.")


if __name__ == "__main__":
    main()
