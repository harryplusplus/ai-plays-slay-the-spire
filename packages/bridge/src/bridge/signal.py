import asyncio
import signal
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import FrameType

Handler = Callable[[int, FrameType | None], None]

_HandlerLike = Handler | int | signal.Handlers | None


@contextmanager
def scoped(handler: Handler, signals: set[int] | None = None) -> Iterator[None]:
    if signals is None:
        signals = {signal.SIGINT, signal.SIGTERM}

    previous = dict[int, _HandlerLike]()
    for sig in signals:
        previous[sig] = signal.getsignal(sig)
        signal.signal(sig, handler)

    try:
        yield
    finally:
        for sig, prev_handler in previous.items():
            signal.signal(sig, prev_handler)


class ToAsyncHandler:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        event: asyncio.Event,
    ) -> None:
        self._loop = loop
        self._event = event

    def __call__(self, _: int, __: FrameType | None) -> None:
        self._loop.call_soon_threadsafe(self._event.set)
