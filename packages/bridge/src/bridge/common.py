import asyncio
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Message:
    id: int
    message: str


MessageQueue = asyncio.Queue[Message]
