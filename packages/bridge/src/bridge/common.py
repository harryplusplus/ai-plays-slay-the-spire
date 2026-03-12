import asyncio
import queue
from dataclasses import dataclass


class Sentinel:
    pass


@dataclass(kw_only=True)
class Message:
    id: int
    message: str


MessageQueue = asyncio.Queue[Message]


@dataclass(kw_only=True)
class Command:
    id: int
    command: str
    future: asyncio.Future[None]


CommandLike = Command | Sentinel

CommandQueue = queue.Queue[CommandLike]
