"""Logging setup for the AI agent."""

import logging
from pathlib import Path

from common.log import create_local_json_formatter, create_rotating_file_handler

AI_LOG = Path.home() / ".sts" / "logs" / "ai.jsonl"
LLM_LOG = Path.home() / ".sts" / "logs" / "llm.jsonl"
REASONING_LOG = Path.home() / ".sts" / "logs" / "reasoning.jsonl"
RUN_LOG = Path.home() / ".sts" / "logs" / "run.jsonl"


def _init_named_logger(
    name: str,
    path: Path,
    level: int = logging.INFO,
    *,
    propagate: bool = False,
) -> None:
    handler = create_rotating_file_handler(path)
    handler.setFormatter(create_local_json_formatter())
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = propagate


def init_logger() -> None:
    _init_named_logger("", Path.home() / ".sts" / "logs" / "ai.jsonl")
    _init_named_logger("ai.run", RUN_LOG)
    _init_named_logger("ai.reasoning", REASONING_LOG, logging.DEBUG)
    _init_named_logger("ai.llm", LLM_LOG, logging.DEBUG)
