from datetime import UTC, datetime

from bridge.models import Base, CommandId, Event, utc_now


def test_utc_now_returns_timezone_aware_utc_datetime() -> None:
    now = utc_now()

    assert isinstance(now, datetime)
    assert now.tzinfo == UTC


def test_command_id_updated_at_utc_normalizes_naive_datetime() -> None:
    updated_at = datetime(2026, 3, 25, 12, 34, 56, tzinfo=UTC).replace(tzinfo=None)
    command_id = CommandId(value=7, updated_at=updated_at)

    assert command_id.updated_at_utc == updated_at.replace(tzinfo=UTC)


def test_models_define_expected_table_names_and_fields() -> None:
    updated_at = datetime(2026, 3, 25, 12, 34, 56, tzinfo=UTC)
    event = Event(
        kind="command",
        data="play",
        created_at=updated_at,
        updated_at=updated_at,
    )

    assert CommandId.__tablename__ == "command_ids"
    assert Event.__tablename__ == "events"
    assert set(Base.metadata.tables) == {"command_ids", "events"}
    assert event.kind == "command"
    assert event.data == "play"
    assert event.created_at == updated_at
    assert event.updated_at == updated_at
