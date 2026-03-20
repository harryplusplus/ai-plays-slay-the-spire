import asyncio
import signal as stdlib_signal
from collections.abc import Iterator
from types import FrameType

import pytest
from bridge import signal


def drain_loop(loop: asyncio.AbstractEventLoop) -> None:
    loop.run_until_complete(asyncio.sleep(0))


@pytest.fixture
def restored_signal_handlers() -> Iterator[None]:
    original_sigint = stdlib_signal.getsignal(stdlib_signal.SIGINT)
    original_sigterm = stdlib_signal.getsignal(stdlib_signal.SIGTERM)

    try:
        yield
    finally:
        stdlib_signal.signal(stdlib_signal.SIGINT, original_sigint)
        stdlib_signal.signal(stdlib_signal.SIGTERM, original_sigterm)


@pytest.mark.usefixtures("restored_signal_handlers")
def test_install_handlers_registers_handler_for_sigint_and_sigterm() -> None:
    def handler(_: int, __: FrameType | None) -> None:
        pass

    signal.install_handlers(handler)

    assert stdlib_signal.getsignal(stdlib_signal.SIGINT) == handler
    assert stdlib_signal.getsignal(stdlib_signal.SIGTERM) == handler


def test_to_async_handler_sets_event() -> None:
    loop = asyncio.new_event_loop()
    event = asyncio.Event()
    handler = signal.ToAsyncHandler(loop, event)

    try:
        handler(stdlib_signal.SIGINT, None)
        drain_loop(loop)

        assert event.is_set() is True
    finally:
        loop.close()
