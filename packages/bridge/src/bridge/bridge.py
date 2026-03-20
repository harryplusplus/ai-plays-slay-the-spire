import asyncio
import sys
from typing import TextIO

from core.db import AsyncSessionmaker
from core.event_repository import AlchemyEventRepository
from core.models import PendingCommand
from core.pending_command_repository import AlchemyPendingCommandRepository

from bridge import message

IDLE_LOOP_SLEEP_SECONDS = 0.1


async def record_message_event(
    sessionmaker: AsyncSessionmaker,
    message: str,
) -> int:
    async with sessionmaker.begin() as session:
        repository = AlchemyEventRepository(session)
        return await repository.add("message", message)


async def skip_pending_commands(
    sessionmaker: AsyncSessionmaker,
) -> int:
    async with sessionmaker.begin() as session:
        event_repository = AlchemyEventRepository(session)
        pending_command_repository = AlchemyPendingCommandRepository(session)
        pending_commands = await pending_command_repository.skip_all_pending()

        for pending_command in pending_commands:
            await event_repository.add("command_skipped", pending_command.command)

        return len(pending_commands)


async def get_next_pending_command(
    sessionmaker: AsyncSessionmaker,
) -> PendingCommand | None:
    async with sessionmaker() as session:
        repository = AlchemyPendingCommandRepository(session)
        return await repository.get_next_pending()


def write_command(command: str, output: TextIO | None = None) -> None:
    resolved = output if output is not None else sys.stdout
    resolved.write(f"{command}\n")
    resolved.flush()


async def process_after_write_command(
    sessionmaker: AsyncSessionmaker,
    pending_command_id: int,
    command: str,
) -> int:
    async with sessionmaker.begin() as session:
        event_repository = AlchemyEventRepository(session)
        pending_command_repository = AlchemyPendingCommandRepository(session)
        event_id = await event_repository.add("command_recorded", command)
        await pending_command_repository.mark_recorded(pending_command_id)
        return event_id


async def process_next_pending_command(
    sessionmaker: AsyncSessionmaker,
    output: TextIO | None = None,
) -> bool:
    pending_command = await get_next_pending_command(sessionmaker)
    if pending_command is None:
        return False

    write_command(pending_command.command, output)
    await process_after_write_command(
        sessionmaker,
        pending_command.id,
        pending_command.command,
    )
    return True


async def process_next(
    sessionmaker: AsyncSessionmaker,
    message_queue: message.Queue,
    stop_event: asyncio.Event,
    output: TextIO | None = None,
) -> bool:
    if stop_event.is_set():
        return False

    message: str | None = None
    has_message = False
    try:
        message = message_queue.get_nowait()
        has_message = True
    except asyncio.QueueEmpty:
        has_message = False

    if has_message:
        if message is None:
            return False

        await record_message_event(sessionmaker, message)
        return True

    if await process_next_pending_command(sessionmaker, output):
        return True

    await asyncio.sleep(IDLE_LOOP_SLEEP_SECONDS)
    return True


async def run(
    sessionmaker: AsyncSessionmaker,
    message_queue: message.Queue,
    stop_event: asyncio.Event,
    output: TextIO | None = None,
) -> None:
    await skip_pending_commands(sessionmaker)

    while await process_next(
        sessionmaker,
        message_queue,
        stop_event,
        output,
    ):
        pass
