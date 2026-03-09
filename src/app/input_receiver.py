import json
import logging
import queue
import sys
from dataclasses import dataclass
from threading import Thread
from typing import cast

logger = logging.getLogger(__name__)


class Eof:
    pass


@dataclass(frozen=True, slots=True)
class Message:
    json_str: str
    data: dict


Input = Eof | Message


InputQueue = queue.Queue[Input]


def main(input_q: InputQueue) -> None:
    for line in sys.stdin:
        json_str = cast(str, line).rstrip()

        logger.debug(json_str)

        try:
            data = json.loads(json_str)
        except ValueError:
            logger.error(f"Invalid JSON: {json_str}")
            continue

        input_q.put(Message(json_str=json_str, data=data))

    input_q.put(Eof())


def start_thread(input_q: InputQueue) -> Thread:
    t = Thread(target=main, args=(input_q,))
    t.start()

    return t
