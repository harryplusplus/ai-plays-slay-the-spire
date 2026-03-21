import asyncio
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def current_thread_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        yield loop
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            asyncio.set_event_loop(None)
            loop.close()
