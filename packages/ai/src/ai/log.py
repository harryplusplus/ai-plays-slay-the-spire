"""JSON Lines logging for the AI agent."""

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, override

from .constants import LLM_LOG, REASONING_LOG, RUN_LOG


class JsonlFormatter(logging.Formatter):
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


def _create_handler(path: Path) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(JsonlFormatter())
    return handler


def _init_root_logger() -> None:
    handler = _create_handler(Path.home() / ".sts" / "logs" / "ai.jsonl")
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


def _init_run_logger() -> None:
    handler = _create_handler(RUN_LOG)
    logger = logging.getLogger("ai.run")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False


def _init_reasoning_logger() -> None:
    handler = _create_handler(REASONING_LOG)
    logger = logging.getLogger("ai.reasoning")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False


def _init_llm_logger() -> None:
    handler = _create_handler(LLM_LOG)
    logger = logging.getLogger("ai.llm")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False


def init_logger() -> None:
    _init_root_logger()
    _init_run_logger()
    _init_reasoning_logger()
    _init_llm_logger()
