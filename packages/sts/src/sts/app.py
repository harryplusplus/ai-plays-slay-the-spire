import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from bridge.db import Db
from bridge.models import Event
from core.event_repository import AlchemyEventRepository
from core.pending_command_repository import AlchemyPendingCommandRepository

app = typer.Typer(add_completion=False, help="Slay the Spire 제어 CLI")


@dataclass(frozen=True, kw_only=True)
class Config:
    sqlite_file: Path


def _get_config(context: typer.Context) -> Config:
    if not isinstance(context.obj, Config):
        raise TypeError("sts app requires Config in context.obj")
    return context.obj


def _format_timestamp(timestamp: datetime) -> str:
    utc_timestamp = (
        timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)
    )
    return utc_timestamp.astimezone().isoformat(timespec="milliseconds")


def _serialize_event(event: Event) -> dict[str, int | str]:
    return {
        "id": event.id,
        "kind": event.kind,
        "data": event.data,
        "created_at": _format_timestamp(event.created_at),
        "updated_at": _format_timestamp(event.updated_at),
    }


def _format_events_json(events: list[Event]) -> str:
    return json.dumps([_serialize_event(event) for event in events], ensure_ascii=False)


async def _record_command(config: Config, command: str) -> None:
    async with Db(config.sqlite_file) as db, db.sessionmaker.begin() as session:
        repository = AlchemyPendingCommandRepository(session)
        await repository.add(command)


async def _read_events_json(config: Config, *, limit: int) -> str:
    async with Db(config.sqlite_file) as db, db.sessionmaker.begin() as session:
        repository = AlchemyEventRepository(session)
        events = await repository.list_recent(limit=limit)
    return _format_events_json(events)


@app.command(help="명령을 추가합니다.")
def command(
    context: typer.Context, command: Annotated[str, typer.Argument(help="추가할 명령")]
) -> None:
    config = _get_config(context)
    asyncio.run(_record_command(config, command))


@app.command(help="최근 이벤트를 조회합니다.")
def events(
    context: typer.Context,
    limit: Annotated[int, typer.Option(help="조회할 이벤트 수")] = 3,
) -> None:
    config = _get_config(context)
    typer.echo(asyncio.run(_read_events_json(config, limit=limit)))
