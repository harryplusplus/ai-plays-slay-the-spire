from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EventKind = Literal["command", "message"]


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


class CommandId(Base):
    __tablename__ = "command_ids"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[int] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    @property
    def updated_at_utc(self) -> datetime:
        return self.updated_at.replace(tzinfo=UTC)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[EventKind] = mapped_column()
    data: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
