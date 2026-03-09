import logging
import queue
from dataclasses import dataclass
from enum import StrEnum
from threading import Thread
from typing import IO


class Kind(StrEnum):
    GAME = "game"
    CODEX = "codex"


@dataclass(frozen=True, slots=True, kw_only=True)
class Message:
    kind: Kind
    data: str | None


MessageQueue = queue.Queue[Message]


def _main(name: str, kind: Kind, io: IO[str], q: MessageQueue) -> None:
    logger = logging.getLogger(name)
    logger.info("started.")

    for line in io:
        data = line.rstrip()
        logger.debug(data)
        q.put(Message(kind=kind, data=data))

    q.put(Message(kind=kind, data=None))
    logger.info("exited.")


class MessageReader:
    def __init__(self, name: str, kind: Kind, io: IO[str], q: MessageQueue) -> None:
        self._t = Thread(target=_main, args=(name, kind, io, q), name=name)
        self._t.start()

    def wait(self) -> None:
        self._t.join()
