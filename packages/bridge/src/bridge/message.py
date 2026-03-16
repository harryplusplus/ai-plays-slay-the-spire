import asyncio
import concurrent.futures
import logging
import sys
import threading
from typing import Protocol, TextIO

from typing_extensions import override

logger = logging.getLogger(__name__)


class MessageReader:
    def __init__(self, in_: TextIO | None = None) -> None:
        self._in: TextIO = in_ if in_ is not None else sys.stdin

    def __call__(self) -> str:
        line = self._in.readline()
        if line == "":
            raise EOFError("MessageReader reached EOF.")
        return line.rstrip()


def _on_done(future: concurrent.futures.Future[None]) -> None:
    try:
        future.result()
    except Exception:
        logger.exception("Error sending message to connection.")


class MessageHandler(Protocol):
    async def __call__(self, message: str) -> None: ...


class MessageReceiverService(Protocol):
    def start(self) -> None: ...


class MessageReceiverServiceImpl(MessageReceiverService):
    def __init__(
        self,
        message_handler: MessageHandler,
        message_reader: MessageReader | None = None,
    ) -> None:
        self._message_handler = message_handler
        self._message_reader = (
            message_reader if message_reader is not None else MessageReader()
        )
        self._thread: threading.Thread | None = None
        self._logger = logger.getChild("MessageReceiverServiceImpl")

    @override
    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._thread = threading.Thread(
            target=self._run,
            args=(loop,),
            daemon=True,
        )
        self._thread.start()

    def _run(self, loop: asyncio.AbstractEventLoop) -> None:
        while True:
            try:
                message = self._message_reader()
            except EOFError:
                self._logger.info(
                    "Stopping loop due to EOFError.",
                )
                break

            future = asyncio.run_coroutine_threadsafe(
                self._message_handler(message),
                loop,
            )
            future.add_done_callback(_on_done)
