from pathlib import Path

import pytest
from core import db
from core.models import PendingCommand
from core.pending_command_repository import AlchemyPendingCommandRepository


@pytest.mark.asyncio
async def test_add_persists_pending_command_with_pending_status(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "pending-add.sqlite")

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        async with sessionmaker() as session:
            pending_command = await session.get(PendingCommand, pending_command_id)

            assert pending_command is not None
            assert pending_command.command == "play"
            assert pending_command.status == "pending"
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_get_next_pending_returns_oldest_pending_command(tmp_path: Path) -> None:
    engine = db.create_engine(tmp_path / "pending-next.sqlite")

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            oldest_pending_id = await repository.add("play")
            recorded_pending_id = await repository.add("state")
            await repository.mark_recorded(recorded_pending_id)
            await repository.add("end")

        async with sessionmaker() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command = await repository.get_next_pending()

            assert pending_command is not None
            assert pending_command.id == oldest_pending_id
            assert pending_command.command == "play"
            assert pending_command.status == "pending"
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_skip_all_pending_marks_only_pending_commands_as_skipped(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "pending-skip.sqlite")

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            skipped_pending_id = await repository.add("play")
            recorded_pending_id = await repository.add("state")
            await repository.mark_recorded(recorded_pending_id)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            skipped_pending_commands = await repository.skip_all_pending()

            assert [
                pending_command.id for pending_command in skipped_pending_commands
            ] == [skipped_pending_id]
            assert [
                pending_command.status for pending_command in skipped_pending_commands
            ] == ["skipped"]

        async with sessionmaker() as session:
            skipped_pending = await session.get(PendingCommand, skipped_pending_id)
            recorded_pending = await session.get(PendingCommand, recorded_pending_id)

            assert skipped_pending is not None
            assert skipped_pending.status == "skipped"
            assert recorded_pending is not None
            assert recorded_pending.status == "recorded"
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_mark_recorded_does_not_overwrite_skipped_status(tmp_path: Path) -> None:
    engine = db.create_engine(tmp_path / "pending-mark-recorded.sqlite")

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            skipped_pending_id = await repository.add("play")
            await repository.skip_all_pending()
            await repository.mark_recorded(skipped_pending_id)

        async with sessionmaker() as session:
            skipped_pending = await session.get(PendingCommand, skipped_pending_id)

            assert skipped_pending is not None
            assert skipped_pending.status == "skipped"
    finally:
        await db.close_engine(engine)
