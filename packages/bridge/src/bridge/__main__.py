import asyncio
import logging
import sys

from core import db
from core.db import AsyncSessionmaker
from core.paths import DB_SQLITE_FILE
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge import bridge, log, message, signal

logger = logging.getLogger(__name__)


async def run(
    engine: AsyncEngine,
    sessionmaker: AsyncSessionmaker,
    message_queue: message.Queue,
    stop_event: asyncio.Event,
) -> None:
    try:
        await db.init(engine)
        await db.init_dev(engine)

        await bridge.run(sessionmaker, message_queue, stop_event)
    finally:
        await db.close_engine(engine)


def main() -> None:
    log.init()
    logger.info("Bridge started.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    stop_event = asyncio.Event()
    signal.install_handlers(signal.ToAsyncHandler(loop, stop_event))

    message_queue = message.Queue()
    message.start_thread(sys.stdin, message.ToAsyncQueue(loop, message_queue))

    engine = db.create_engine(DB_SQLITE_FILE)
    sessionmaker = AsyncSessionmaker(engine)

    try:
        loop.run_until_complete(run(engine, sessionmaker, message_queue, stop_event))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        asyncio.set_event_loop(None)

    logger.info("Bridge closed.")


if __name__ == "__main__":
    main()
