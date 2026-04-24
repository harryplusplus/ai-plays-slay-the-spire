"""JSON Lines logging for the AI agent."""

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, override


class JsonlFormatter(logging.Formatter):
    """Format log records as JSON Lines."""

    _STANDARD_ATTRS = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "asctime",
            "taskName",
        },
    )

    @override
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": (
                datetime.fromtimestamp(record.created)
                .astimezone()
                .isoformat(timespec="milliseconds")
            ),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        entry |= {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._STANDARD_ATTRS and not key.startswith("_")
        }
        return json.dumps(entry, ensure_ascii=False, default=str)


def init_logger() -> None:
    handler = RotatingFileHandler(
        Path.home() / ".sts" / "logs" / "ai.jsonl",
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(JsonlFormatter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    logging.getLogger("ai").setLevel(logging.DEBUG)
