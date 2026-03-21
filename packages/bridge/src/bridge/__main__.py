import asyncio
import logging
import sys

from core import db
from core.paths import DB_SQLITE_FILE

from bridge import bridge, log, message, signal

logger = logging.getLogger(__name__)


async def run(
    message_queue: message.Queue,
    stop_event: asyncio.Event,
) -> None:
    async with db.Db(DB_SQLITE_FILE, init_dev=True) as bridge_db:
        await bridge.run(bridge_db.sessionmaker, message_queue, stop_event)


def main() -> None:
    log.init()
    logger.info("Bridge started.")

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)

        stop_event = asyncio.Event()
        signal.install_handlers(signal.ToAsyncHandler(loop, stop_event))

        message_queue = message.Queue()
        message.start_thread(sys.stdin, message.ToAsyncQueue(loop, message_queue))

        loop.run_until_complete(run(message_queue, stop_event))
    except Exception:
        logger.exception("An error occurred in the main loop.")
        raise
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            logger.exception("An error occurred while shutting down async generators.")
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    logger.info("Bridge closed.")


if __name__ == "__main__":
    main()
