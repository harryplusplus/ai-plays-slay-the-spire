from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Any, override

from pythonjsonlogger.json import JsonFormatter

if TYPE_CHECKING:
    from logging import LogRecord
    from pathlib import Path


class LocalJsonFormatter(JsonFormatter):
    @override
    def add_fields(
        self,
        log_data: dict[str, Any],
        record: LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_data, record, message_dict)
        log_data["timestamp"] = (
            datetime.fromtimestamp(record.created)
            .astimezone()
            .isoformat(timespec="milliseconds")
        )


def create_local_json_formatter() -> LocalJsonFormatter:
    return LocalJsonFormatter(
        fmt=["name", "levelname", "message"],
        json_ensure_ascii=False,
    )


def create_rotating_file_handler(path: Path) -> RotatingFileHandler:
    return RotatingFileHandler(
        path,
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
