"""JSON Lines logging for the AI agent."""

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from .constants import LLM_DUMP_DIR, MAX_DUMPS, REASONING_LOG, RUN_LOG

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam


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


def _create_handler(path: Path) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(JsonlFormatter())
    return handler


def init_ai_logger() -> None:
    handler = _create_handler(Path.home() / ".sts" / "logs" / "ai.jsonl")
    logger = logging.getLogger("ai")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False


def init_run_logger() -> None:
    handler = _create_handler(RUN_LOG)
    logger = logging.getLogger("run")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False


def init_reasoning_logger() -> None:
    """Set up reasoning.jsonl handler on reasoning logger."""
    handler = _create_handler(REASONING_LOG)
    logger = logging.getLogger("reasoning")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False


def dump_messages(messages: list[ChatCompletionMessageParam]) -> None:
    """Dump the messages array to a file before LLM API call.
    Keeps only the last MAX_DUMPS dumps (action-based rotation).
    """
    LLM_DUMP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")  # noqa: UP017
    filepath = LLM_DUMP_DIR / f"llm_dump_{timestamp}.json"

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    dumps = sorted(LLM_DUMP_DIR.glob("llm_dump_*.json"))
    while len(dumps) > MAX_DUMPS:
        oldest = dumps.pop(0)
        oldest.unlink()
