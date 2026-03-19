import asyncio
import logging
import signal
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Protocol, TextIO, TypeVar

from core import db
from core.paths import DB_SQLITE_FILE
from sqlalchemy.ext.asyncio import AsyncEngine

from bridge import bridge, log
from bridge.message import MessageQueue, start_message_thread

logger = logging.getLogger(__name__)
T = TypeVar("T")

SignalHandler = Callable[[int, FrameType | None], None]
RegisterSignalHandler = Callable[[int, SignalHandler], object]
LoggingInitializer = Callable[[], None]
MessageQueueFactory = Callable[[], MessageQueue]
CreateEngine = Callable[[Path], AsyncEngine]
CreateSessionmaker = Callable[[AsyncEngine], db.AsyncSessionmaker]
MainRunner = Callable[
    [AsyncEngine, db.AsyncSessionmaker, MessageQueue, asyncio.Event, TextIO],
    Awaitable[None],
]
StopEventFactory = Callable[[], asyncio.Event]
StartMessageThread = Callable[
    [TextIO, asyncio.AbstractEventLoop, MessageQueue],
    object,
]
SetEventLoop = Callable[[asyncio.AbstractEventLoop | None], None]


class SignalLoop(Protocol):
    def call_soon_threadsafe(
        self,
        callback: Callable[..., object],
        *args: object,
    ) -> object: ...


def request_stop(signal_name: str, stop_event: asyncio.Event) -> None:
    logger.info("Received %s. Shutting down.", signal_name)
    stop_event.set()


def install_signal_handlers(
    loop: SignalLoop,
    stop_event: asyncio.Event,
    *,
    register_signal_handler: RegisterSignalHandler = signal.signal,
) -> None:
    def on_signal(signum: int, _: FrameType | None) -> None:
        signal_name = signal.Signals(signum).name
        loop.call_soon_threadsafe(request_stop, signal_name, stop_event)

    register_signal_handler(signal.SIGINT, on_signal)
    register_signal_handler(signal.SIGTERM, on_signal)


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


@dataclass(frozen=True)
class ApplicationDeps:
    initialize_logging: LoggingInitializer = log.init
    loop_factory: Callable[[], asyncio.AbstractEventLoop] = asyncio.new_event_loop
    set_event_loop: SetEventLoop = asyncio.set_event_loop
    stop_event_factory: StopEventFactory = asyncio.Event
    message_queue_factory: MessageQueueFactory = MessageQueue
    install_signal_handlers_fn: Callable[[SignalLoop, asyncio.Event], None] = (
        install_signal_handlers
    )
    start_message_thread_fn: StartMessageThread = start_message_thread
    main_fn: MainRunner = main


DEFAULT_APPLICATION_DEPS = ApplicationDeps()


def run_application(
    engine: AsyncEngine,
    sessionmaker: db.AsyncSessionmaker,
    input_stream: TextIO,
    output_stream: TextIO,
    deps: ApplicationDeps = DEFAULT_APPLICATION_DEPS,
) -> None:
    deps.initialize_logging()
    logger.info("Bridge started.")

    loop = deps.loop_factory()
    deps.set_event_loop(loop)

    stop_event = deps.stop_event_factory()
    message_queue = deps.message_queue_factory()
    deps.install_signal_handlers_fn(loop, stop_event)

    _message_thread = deps.start_message_thread_fn(
        input_stream,
        loop,
        message_queue,
    )
    try:
        loop.run_until_complete(
            deps.main_fn(engine, sessionmaker, message_queue, stop_event, output_stream)
        )
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        deps.set_event_loop(None)

    logger.info("Bridge closed.")


@dataclass(frozen=True)
class CliDeps:
    create_engine: CreateEngine = db.create_engine
    create_sessionmaker: CreateSessionmaker = db.create_sessionmaker
    run_application_fn: Callable[
        [AsyncEngine, db.AsyncSessionmaker, TextIO, TextIO],
        None,
    ] = run_application


DEFAULT_CLI_DEPS = CliDeps()


def run_cli(
    sqlite_file: Path = DB_SQLITE_FILE,
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
    deps: CliDeps = DEFAULT_CLI_DEPS,
) -> None:
    engine = deps.create_engine(sqlite_file)
    sessionmaker = deps.create_sessionmaker(engine)
    deps.run_application_fn(engine, sessionmaker, input_stream, output_stream)


if __name__ == "__main__":  # pragma: no cover
    run_cli()
