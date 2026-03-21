from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EventKind = Literal["command_recorded", "command_skipped", "message"]


class Base(DeclarativeBase):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[EventKind] = mapped_column()
    data: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=_utc_now, onupdate=_utc_now)


PendingCommandStatus = Literal["pending", "recorded", "skipped"]


class PendingCommand(Base):
    __tablename__ = "pending_commands"

    id: Mapped[int] = mapped_column(primary_key=True)
    command: Mapped[str] = mapped_column()
    status: Mapped[PendingCommandStatus] = mapped_column(default="pending")
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=_utc_now, onupdate=_utc_now)
