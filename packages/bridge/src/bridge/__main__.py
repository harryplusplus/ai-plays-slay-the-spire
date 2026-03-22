import asyncio
import logging
import sys

from core import event_loop
from core.db import Db
from core.paths import DB_SQLITE

from bridge import bridge, log, message, signal

logger = logging.getLogger(__name__)


async def run(
    message_queue: message.Queue,
    stop_event: asyncio.Event,
) -> None:
    async with Db(DB_SQLITE, should_create_schema=True) as db:
        await bridge.run(db.sessionmaker, message_queue, stop_event)


def main() -> None:
    log.init()
    logger.info("Bridge started.")

    with event_loop.install() as loop:
        stop_event = asyncio.Event()

        with signal.install(signal.ToAsyncHandler(loop, stop_event)):
            message_queue = message.Queue()
            message.start_thread(sys.stdin, message.ToAsyncQueue(loop, message_queue))

            loop.run_until_complete(run(message_queue, stop_event))

    logger.info("Bridge closed.")


if __name__ == "__main__":
    main()
