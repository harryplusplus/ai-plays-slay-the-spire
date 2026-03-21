import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import typer
from core import event_loop
from core.db import AsyncSessionmaker, Db
from core.event_repository import AlchemyEventRepository
from core.models import Event
from core.paths import DB_SQLITE_FILE
from core.pending_command_repository import AlchemyPendingCommandRepository

from sts import log

app = typer.Typer(add_completion=False, help="Slay the Spire 제어 CLI")


@dataclass(frozen=True, kw_only=True)
class State:
    loop: asyncio.AbstractEventLoop
    sessionmaker: AsyncSessionmaker


@contextmanager
def state() -> Iterator[State]:
    with event_loop.install() as loop:
        db = Db(DB_SQLITE_FILE)
        try:
            loop.run_until_complete(db.open())
            state = State(loop=loop, sessionmaker=db.sessionmaker)
            yield state
        finally:
            loop.run_until_complete(db.close())


def get_state(context: typer.Context) -> State:
    return context.obj


def _format_timestamp(timestamp: datetime) -> str:
    utc_timestamp = (
        timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)
    )
    return utc_timestamp.isoformat(timespec="milliseconds")


def _serialize_event(event: Event) -> dict[str, int | str]:
    return {
        "id": event.id,
        "kind": event.kind,
        "data": event.data,
        "created_at": _format_timestamp(event.created_at),
        "updated_at": _format_timestamp(event.updated_at),
    }


def _format_events_json(events: list[Event]) -> str:
    return json.dumps(
        [_serialize_event(event) for event in events],
        ensure_ascii=False,
        indent=2,
    )


async def _format_recent_events_json(
    sessionmaker: AsyncSessionmaker, *, limit: int
) -> str:
    async with sessionmaker.begin() as session:
        repository = AlchemyEventRepository(session)
        events = await repository.list_recent(limit=limit)
    return _format_events_json(events)


@app.callback()
def main(context: typer.Context) -> None:
    log.init()
    context.obj = context.with_resource(state())


@app.command(help="명령을 추가합니다.")
def command(
    context: typer.Context, command: Annotated[str, typer.Argument(help="추가할 명령")]
) -> None:
    state = get_state(context)

    async def run() -> None:
        async with state.sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            await repository.add(command)

    state.loop.run_until_complete(run())


@app.command(help="최근 이벤트를 조회합니다.")
def events(
    context: typer.Context,
    limit: Annotated[int, typer.Option(help="조회할 이벤트 수")] = 3,
) -> None:
    state = get_state(context)
    json_output = state.loop.run_until_complete(
        _format_recent_events_json(state.sessionmaker, limit=limit)
    )
    typer.echo(json_output)


def cli() -> None:
    app()
