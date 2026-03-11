import logging
import sys
import threading
from collections import deque

from bridge import command

Message = str

logger = logging.getLogger(__name__)


def _check_running(*, running: bool) -> None:
    if not running:
        raise RuntimeError(
            "Message runner is not running.",
        )


class Context:
    def __init__(self) -> None:
        self.messages = deque[Message]()
        self.running = False
        self.lock = threading.Lock()


class Accessor:
    def __init__(self, context: Context) -> None:
        self._context = context

    def get_all(self) -> list[Message]:
        with self._context.lock:
            _check_running(running=self._context.running)
            return list[Message](self._context.messages)


class Runner:
    def __init__(self, command_writer: command.Writer) -> None:
        self._context = Context()
        self._command_writer = command_writer

    def run(self) -> None:
        with self._context.lock:
            if self._context.running:
                raise RuntimeError(
                    "Message runner is already running.",
                )

            self._context.running = True

        logger.info("Started. Press Ctrl+D to exit.")
        self._command_writer.write_sync("ready")

        for line in sys.stdin:
            message = line.rstrip()
            with self._context.lock:
                self._context.messages.append(message)

        with self._context.lock:
            self._context.running = False

        logger.info("Exited.")

    def accessor(self) -> Accessor:
        return Accessor(self._context)
