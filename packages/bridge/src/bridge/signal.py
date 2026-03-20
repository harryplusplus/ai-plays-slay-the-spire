import asyncio
import signal
from collections.abc import Callable
from types import FrameType

Handler = Callable[[int, FrameType | None], None]


def install_handlers(handler: Handler) -> None:
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


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
