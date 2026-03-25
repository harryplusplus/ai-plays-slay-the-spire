from typing import Protocol

from typing_extensions import override

from bridge.command_id_repository import CommandIdRepository
from bridge.db import Db
from bridge.models import CommandId


class CommandIdService(Protocol):
    async def next(self) -> CommandId: ...


class CommandIdServiceImpl(CommandIdService):
    def __init__(self, db: Db) -> None:
        self._db = db

    @override
    async def next(self) -> CommandId:
        async with self._db.sessionmaker.begin() as session:
            return await CommandIdRepository(session).next()
