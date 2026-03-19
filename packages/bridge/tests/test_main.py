import asyncio
import io
import signal
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

import pytest
from bridge import __main__
from bridge.message import MessageQueue
from core import db
from core.models import Event
from sqlalchemy.ext.asyncio import AsyncEngine

RUN_UNTIL_COMPLETE_CALLS = 2


class RecordingLoop:
    scheduled_calls: list[tuple[Callable[..., object], tuple[object, ...]]]

    def __init__(self) -> None:
        self.scheduled_calls = []

    def call_soon_threadsafe(
        self,
        callback: Callable[..., object],
        *args: object,
    ) -> object:
        self.scheduled_calls.append((callback, args))
        return callback(*args)


class RecordingSignalRegistrar:
    handlers: dict[int, __main__.SignalHandler]

    def __init__(self) -> None:
        self.handlers = {}

    def __call__(
        self,
        signum: int,
        handler: __main__.SignalHandler,
    ) -> object:
        self.handlers[signum] = handler
        return object()


class EventLoopSetter:
    calls: list[asyncio.AbstractEventLoop | None]

    def __init__(self) -> None:
        self.calls = []

    def __call__(self, loop: asyncio.AbstractEventLoop | None) -> None:
        self.calls.append(loop)


class LoggingInitializer:
    call_count: int

    def __init__(self) -> None:
        self.call_count = 0

    def __call__(self) -> None:
        self.call_count += 1


class SignalInstaller:
    calls: list[tuple[__main__.SignalLoop, asyncio.Event]]

    def __init__(self) -> None:
        self.calls = []

    def __call__(self, loop: __main__.SignalLoop, stop_event: asyncio.Event) -> None:
        self.calls.append((loop, stop_event))


class ThreadStarter:
    calls: list[tuple[TextIO, asyncio.AbstractEventLoop, MessageQueue]]

    def __init__(self) -> None:
        self.calls = []

    def __call__(
        self,
        input_stream: TextIO,
        loop: asyncio.AbstractEventLoop,
        queue: MessageQueue,
    ) -> object:
        self.calls.append((input_stream, loop, queue))
        return object()


class MainRunner:
    calls: list[
        tuple[
            AsyncEngine,
            db.AsyncSessionmaker,
            MessageQueue,
            asyncio.Event,
            TextIO,
        ]
    ]

    def __init__(self) -> None:
        self.calls = []

    async def __call__(
        self,
        engine: AsyncEngine,
        sessionmaker: db.AsyncSessionmaker,
        message_queue: MessageQueue,
        stop_event: asyncio.Event,
        output_stream: TextIO,
    ) -> None:
        self.calls.append(
            (engine, sessionmaker, message_queue, stop_event, output_stream)
        )


class ApplicationRunner:
    calls: list[tuple[AsyncEngine, db.AsyncSessionmaker, TextIO, TextIO]]

    def __init__(self) -> None:
        self.calls = []

    def __call__(
        self,
        engine: AsyncEngine,
        sessionmaker: db.AsyncSessionmaker,
        input_stream: TextIO,
        output_stream: TextIO,
    ) -> None:
        self.calls.append((engine, sessionmaker, input_stream, output_stream))


def test_request_stop_sets_stop_event() -> None:
    stop_event = asyncio.Event()

    __main__.request_stop("SIGINT", stop_event)

    assert stop_event.is_set() is True


def test_install_signal_handlers_registers_sigint_and_sigterm() -> None:
    loop = RecordingLoop()
    stop_event = asyncio.Event()
    register_signal_handler = RecordingSignalRegistrar()

    __main__.install_signal_handlers(
        loop,
        stop_event,
        register_signal_handler=register_signal_handler,
    )

    assert signal.SIGINT in register_signal_handler.handlers
    assert signal.SIGTERM in register_signal_handler.handlers

    handler = register_signal_handler.handlers[signal.SIGINT]
    handler(signal.SIGINT, None)

    assert stop_event.is_set() is True
    assert len(loop.scheduled_calls) == 1
    assert loop.scheduled_calls[0][0] is __main__.request_stop
    assert loop.scheduled_calls[0][1] == ("SIGINT", stop_event)


def test_run_application_wires_loop_signals_thread_and_main(
    tmp_path: Path,
) -> None:
    sqlite_file = tmp_path / "run-application.sqlite"
    engine = db.create_engine(sqlite_file)
    sessionmaker = db.create_sessionmaker(engine)
    input_stream = io.StringIO("")
    output_stream = io.StringIO()
    loop = asyncio.new_event_loop()
    set_event_loop = EventLoopSetter()
    initialize_logging = LoggingInitializer()
    install_signal_handlers_fn = SignalInstaller()
    start_message_thread_fn = ThreadStarter()
    main_fn = MainRunner()
    stop_event = asyncio.Event()
    message_queue = MessageQueue()

    try:
        __main__.run_application(
            engine,
            sessionmaker,
            input_stream,
            output_stream,
            __main__.ApplicationDeps(
                initialize_logging=initialize_logging,
                loop_factory=lambda: loop,
                set_event_loop=set_event_loop,
                stop_event_factory=lambda: stop_event,
                message_queue_factory=lambda: message_queue,
                install_signal_handlers_fn=install_signal_handlers_fn,
                start_message_thread_fn=start_message_thread_fn,
                main_fn=main_fn,
            ),
        )
    finally:
        asyncio.run(db.close_engine(engine))

    assert initialize_logging.call_count == 1
    assert set_event_loop.calls == [loop, None]
    assert install_signal_handlers_fn.calls == [(loop, stop_event)]
    assert start_message_thread_fn.calls == [(input_stream, loop, message_queue)]
    assert main_fn.calls == [
        (engine, sessionmaker, message_queue, stop_event, output_stream),
    ]
    assert loop.is_closed() is True


def test_run_cli_creates_dependencies_and_runs_application(
    tmp_path: Path,
) -> None:
    sqlite_file = tmp_path / "run-cli.sqlite"
    engine = db.create_engine(sqlite_file)
    sessionmaker = db.create_sessionmaker(engine)
    input_stream = io.StringIO("")
    output_stream = io.StringIO()
    run_application_fn = ApplicationRunner()
    create_engine_calls: list[Path] = []
    create_sessionmaker_calls: list[AsyncEngine] = []

    def create_engine(sqlite_file: Path) -> AsyncEngine:
        create_engine_calls.append(sqlite_file)
        return engine

    def create_sessionmaker(engine: AsyncEngine) -> db.AsyncSessionmaker:
        create_sessionmaker_calls.append(engine)
        return sessionmaker

    try:
        __main__.run_cli(
            sqlite_file,
            input_stream,
            output_stream,
            __main__.CliDeps(
                create_engine=create_engine,
                create_sessionmaker=create_sessionmaker,
                run_application_fn=run_application_fn,
            ),
        )
    finally:
        asyncio.run(db.close_engine(engine))

    assert create_engine_calls == [sqlite_file]
    assert create_sessionmaker_calls == [engine]
    assert run_application_fn.calls == [
        (engine, sessionmaker, input_stream, output_stream),
    ]


@pytest.mark.asyncio
async def test_main_persists_received_message_events(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "bridge.sqlite"
    engine = db.create_engine(sqlite_file)
    sessionmaker = db.create_sessionmaker(engine)
    message_queue = MessageQueue()
    stop_event = asyncio.Event()
    message_queue.put_nowait("play")
    message_queue.put_nowait(None)

    await __main__.main(
        engine,
        sessionmaker,
        message_queue,
        stop_event,
        io.StringIO(),
    )

    verify_engine = db.create_engine(sqlite_file)
    verify_sessionmaker = db.create_sessionmaker(verify_engine)
    try:
        async with verify_sessionmaker() as session:
            event = await session.get(Event, 1)

            assert event is not None
            assert event.kind == "message"
            assert event.data == "play"
    finally:
        await db.close_engine(verify_engine)
