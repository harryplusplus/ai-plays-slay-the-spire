from pathlib import Path

import pytest
from bridge.command_id_service import CommandIdServiceImpl
from bridge.db import Db
from bridge.models import CommandId

INITIAL_COMMAND_ID_VALUE = 1
NEXT_COMMAND_ID_VALUE = 2


@pytest.mark.asyncio
async def test_next_returns_incremented_command_id_and_persists_it(
    tmp_path: Path,
) -> None:
    database = Db(tmp_path / "command-id-service.sqlite")
    service = CommandIdServiceImpl(database)
    await database.init()

    try:
        first_command_id = await service.next()
        second_command_id = await service.next()

        assert first_command_id.id == INITIAL_COMMAND_ID_VALUE
        assert first_command_id.value == INITIAL_COMMAND_ID_VALUE
        assert second_command_id.id == INITIAL_COMMAND_ID_VALUE
        assert second_command_id.value == NEXT_COMMAND_ID_VALUE

        async with database.sessionmaker() as session:
            stored_command_id = await session.get(CommandId, INITIAL_COMMAND_ID_VALUE)

            assert stored_command_id is not None
            assert stored_command_id.value == NEXT_COMMAND_ID_VALUE
    finally:
        await database.close()
