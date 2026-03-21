import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from core.db import Db
from core.event_repository import AlchemyEventRepository
from sts import app


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


@pytest.mark.asyncio
async def test_format_recent_events_json_returns_oldest_first_json_array(
    tmp_path: Path,
) -> None:
    db = Db(tmp_path / "events.sqlite", should_create_schema=True)

    async with db:
        async with db.sessionmaker.begin() as session:
            repository = AlchemyEventRepository(session)
            await repository.add("command_recorded", "first")
            await repository.add("message", "second")
            await repository.add("command_skipped", "third")

        json_output = await app._format_recent_events_json(db.sessionmaker, limit=2)

    parsed_output = json.loads(json_output)

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
