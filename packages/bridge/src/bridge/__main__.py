import asyncio
import logging
import signal
import sys
from types import FrameType
from typing import TextIO

from core import db
from core.paths import DB_SQLITE_FILE
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge import bridge, log
from bridge.message import MessageQueue, start_message_thread

logger = logging.getLogger(__name__)


def request_stop(signal_name: str, stop_event: asyncio.Event) -> None:
    logger.info("Received %s. Shutting down.", signal_name)
    stop_event.set()


def install_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    stop_event: asyncio.Event,
) -> None:
    def on_signal(signum: int, _: FrameType | None) -> None:
        signal_name = signal.Signals(signum).name
        loop.call_soon_threadsafe(request_stop, signal_name, stop_event)

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)


async def main(
    engine: AsyncEngine,
    sessionmaker: db.AsyncSessionmaker,
    message_queue: MessageQueue,
    stop_event: asyncio.Event,
    output_stream: TextIO,
) -> None:
    try:
        await db.init(engine)
        await db.init_dev(engine)
        await bridge.run(
            sessionmaker,
            message_queue,
            stop_event,
            output_stream,
        )

    finally:
        await db.close_engine(engine)


if __name__ == "__main__":
    log.init()
    logger.info("Bridge started.")

    engine = db.create_engine(DB_SQLITE_FILE)
    sessionmaker = db.create_sessionmaker(engine)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    stop_event = asyncio.Event()
    message_queue = MessageQueue()
    install_signal_handlers(loop, stop_event)

    _message_thread = start_message_thread(
        input_stream=sys.stdin,
        loop=loop,
        queue=message_queue,
    )
    try:
        loop.run_until_complete(
            main(engine, sessionmaker, message_queue, stop_event, sys.stdout)
        )
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        asyncio.set_event_loop(None)

    logger.info("Bridge closed.")
