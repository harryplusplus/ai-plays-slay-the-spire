from bridge.command_id_repository import CommandIdRepository
from bridge.db import Db
from bridge.models import CommandId


class CommandIdService:
    def __init__(self, db: Db) -> None:
        self._db = db

    async def next(self) -> CommandId:
        async with self._db.sessionmaker.begin() as session:
            return await CommandIdRepository(session).next()
