from pathlib import Path

import pytest
from bridge.command_id_repository import CommandIdRepository
from bridge.db import Db
from bridge.models import CommandId
from sqlalchemy import func, select

INITIAL_COMMAND_ID_VALUE = 1
NEXT_COMMAND_ID_VALUE = 2


@pytest.mark.asyncio
async def test_next_creates_initial_command_id_row(tmp_path: Path) -> None:
    database = Db(tmp_path / "command-id.sqlite")
    await database.init()

    try:
        async with database.sessionmaker.begin() as session:
            repository = CommandIdRepository(session)
            command_id = await repository.next()

        assert command_id.id == INITIAL_COMMAND_ID_VALUE
        assert command_id.value == INITIAL_COMMAND_ID_VALUE

        async with database.sessionmaker() as session:
            stored_command_id = await session.get(CommandId, INITIAL_COMMAND_ID_VALUE)

            assert stored_command_id is not None
            assert stored_command_id.id == INITIAL_COMMAND_ID_VALUE
            assert stored_command_id.value == INITIAL_COMMAND_ID_VALUE
            assert stored_command_id.updated_at == command_id.updated_at
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_next_updates_existing_command_id_row_in_place(tmp_path: Path) -> None:
    database = Db(tmp_path / "command-id-update.sqlite")
    await database.init()

    try:
        async with database.sessionmaker.begin() as session:
            repository = CommandIdRepository(session)
            await repository.next()

        async with database.sessionmaker.begin() as session:
            repository = CommandIdRepository(session)
            command_id = await repository.next()

        assert command_id.id == INITIAL_COMMAND_ID_VALUE
        assert command_id.value == NEXT_COMMAND_ID_VALUE

        async with database.sessionmaker() as session:
            row_count = await session.scalar(
                select(func.count()).select_from(CommandId)
            )
            stored_command_id = await session.get(CommandId, INITIAL_COMMAND_ID_VALUE)

            assert row_count == INITIAL_COMMAND_ID_VALUE
            assert stored_command_id is not None
            assert stored_command_id.value == NEXT_COMMAND_ID_VALUE
            assert stored_command_id.updated_at == command_id.updated_at
    finally:
        await database.close()
