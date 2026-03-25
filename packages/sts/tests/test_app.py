import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from bridge.db import Db
from bridge.models import PendingCommand
from core.event_repository import AlchemyEventRepository
from sts import app
from typer.testing import CliRunner

runner = CliRunner()


def _create_schema(sqlite_file: Path) -> None:
    async def run() -> None:
        async with Db(sqlite_file, should_create_schema=True):
            return

    asyncio.run(run())


def _seed_events(sqlite_file: Path) -> None:
    async def run() -> None:
        async with (
            Db(
                sqlite_file,
                should_create_schema=True,
            ) as db,
            db.sessionmaker.begin() as session,
        ):
            repository = AlchemyEventRepository(session)
            await repository.add("command_recorded", "first")
            await repository.add("message", "second")
            await repository.add("command_skipped", "third")

    asyncio.run(run())


def _read_pending_command(
    sqlite_file: Path, pending_command_id: int
) -> tuple[int, str, str] | None:
    async def run() -> tuple[int, str, str] | None:
        async with Db(sqlite_file) as db, db.sessionmaker() as session:
            pending_command = await session.get(PendingCommand, pending_command_id)

            if pending_command is None:
                return None

            return (
                pending_command.id,
                pending_command.command,
                pending_command.status,
            )

    return asyncio.run(run())


def test_format_events_json_returns_empty_array() -> None:
    assert app._format_events_json([]) == "[]"


def test_format_timestamp_converts_utc_timestamp_to_local_timezone() -> None:
    timestamp = datetime(2026, 3, 20, 14, 32, 42, 376000, tzinfo=UTC)

    assert app._format_timestamp(timestamp) == timestamp.astimezone().isoformat(
        timespec="milliseconds"
    )


def test_format_timestamp_assumes_naive_timestamp_is_utc() -> None:
    timestamp = datetime(2026, 3, 20, 14, 32, 42, 376000, tzinfo=UTC).replace(
        tzinfo=None
    )

    assert app._format_timestamp(timestamp) == timestamp.replace(
        tzinfo=UTC
    ).astimezone().isoformat(timespec="milliseconds")


def test_events_command_requires_config_in_context_object() -> None:
    result = runner.invoke(app.app, ["events"], catch_exceptions=True)

    assert result.exit_code == 1
    assert isinstance(result.exception, TypeError)
    assert str(result.exception) == "sts app requires Config in context.obj"


def test_command_command_records_pending_command(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "command.sqlite"
    _create_schema(sqlite_file)

    result = runner.invoke(
        app.app,
        ["command", "play"],
        obj=app.Config(sqlite_file=sqlite_file),
    )

    assert result.exit_code == 0
    assert _read_pending_command(sqlite_file, pending_command_id=1) == (
        1,
        "play",
        "pending",
    )


def test_events_command_outputs_recent_events_json(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "events.sqlite"
    _seed_events(sqlite_file)

    result = runner.invoke(
        app.app,
        ["events", "--limit", "2"],
        obj=app.Config(sqlite_file=sqlite_file),
    )

    assert result.exit_code == 0

    parsed_output = json.loads(result.output)

    assert [
        {
            key: value
            for key, value in event.items()
            if key not in {"created_at", "updated_at"}
        }
        for event in parsed_output
    ] == [
        {
            "id": 2,
            "kind": "message",
            "data": "second",
        },
        {
            "id": 3,
            "kind": "command_skipped",
            "data": "third",
        },
    ]

    for event in parsed_output:
        assert datetime.fromisoformat(event["created_at"]).tzinfo is not None
        assert datetime.fromisoformat(event["updated_at"]).tzinfo is not None
