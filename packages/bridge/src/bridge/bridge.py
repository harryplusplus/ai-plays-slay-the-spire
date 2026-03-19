import asyncio
from typing import TextIO

from core import db
from core.event_repository import AlchemyEventRepository
from core.models import PendingCommand
from core.pending_command_repository import AlchemyPendingCommandRepository

from bridge.message import MessageQueue

IDLE_LOOP_SLEEP_SECONDS = 0.0


async def record_message_event(
    sessionmaker: db.AsyncSessionmaker,
    message: str,
) -> int:
    async with sessionmaker.begin() as session:
        repository = AlchemyEventRepository(session)
        return await repository.add("message", message)


async def skip_pending_commands_at_startup(
    sessionmaker: db.AsyncSessionmaker,
) -> int:
    async with sessionmaker.begin() as session:
        event_repository = AlchemyEventRepository(session)
        pending_command_repository = AlchemyPendingCommandRepository(session)
        pending_commands = await pending_command_repository.skip_all_pending()

        for pending_command in pending_commands:
            await event_repository.add("command_skipped", pending_command.command)

        return len(pending_commands)


async def get_next_pending_command(
    sessionmaker: db.AsyncSessionmaker,
) -> PendingCommand | None:
    async with sessionmaker() as session:
        repository = AlchemyPendingCommandRepository(session)
        return await repository.get_next_pending()


def write_command(output_stream: TextIO, command: str) -> None:
    output_stream.write(f"{command}\n")
    output_stream.flush()


async def record_command_event_and_mark_pending_command_recorded(
    sessionmaker: db.AsyncSessionmaker,
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
    sessionmaker: db.AsyncSessionmaker,
    output_stream: TextIO,
) -> bool:
    pending_command = await get_next_pending_command(sessionmaker)
    if pending_command is None:
        return False

    write_command(output_stream, pending_command.command)
    await record_command_event_and_mark_pending_command_recorded(
        sessionmaker,
        pending_command.id,
        pending_command.command,
    )
    return True


async def process_next_iteration(
    sessionmaker: db.AsyncSessionmaker,
    message_queue: MessageQueue,
    stop_event: asyncio.Event,
    output_stream: TextIO,
) -> bool:
    if stop_event.is_set():
        return False

    try:
        message = message_queue.get_nowait()
    except asyncio.QueueEmpty:
        message = None
        has_message = False
    else:
        has_message = True

    if has_message:
        if message is None:
            return False

        await record_message_event(sessionmaker, message)
        return True

    if await process_next_pending_command(sessionmaker, output_stream):
        return True

    await asyncio.sleep(IDLE_LOOP_SLEEP_SECONDS)
    return True


async def run(
    sessionmaker: db.AsyncSessionmaker,
    message_queue: MessageQueue,
    stop_event: asyncio.Event,
    output_stream: TextIO,
) -> None:
    await skip_pending_commands_at_startup(sessionmaker)

    while await process_next_iteration(
        sessionmaker,
        message_queue,
        stop_event,
        output_stream,
    ):
        pass
