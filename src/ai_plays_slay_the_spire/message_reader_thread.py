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


def _main(name: str, kind: Kind, io: IO[str], q: queue.Queue[Message]) -> None:
    logger = logging.getLogger(name)
    logger.info("started.")

    for line in io:
        data = line.rstrip()
        logger.debug(data)
        q.put(Message(kind=kind, data=data))

    q.put(Message(kind=kind, data=None))
    logger.info("exited.")


def start(name: str, kind: Kind, io: IO[str], q: queue.Queue[Message]) -> Thread:
    t = Thread(target=_main, args=(name, kind, io, q), name=name)
    t.start()

    return t
