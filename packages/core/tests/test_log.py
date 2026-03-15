# ruff: noqa: S101

import datetime
import inspect
import io
import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from core import log


class _StringableValue:
    def __str__(self) -> str:
        return "stringable"


@pytest.fixture
def isolated_root_logger() -> Iterator[logging.Logger]:
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers.copy()
    original_level = root_logger.level

    for handler in original_handlers:
        root_logger.removeHandler(handler)

    try:
        yield root_logger
    finally:
        for handler in root_logger.handlers.copy():
            root_logger.removeHandler(handler)
            handler.close()

        root_logger.setLevel(original_level)

        for handler in original_handlers:
            root_logger.addHandler(handler)


def test_init_sets_root_logger_level_and_creates_logs_dir(
    isolated_root_logger: logging.Logger,
    tmp_path: Path,
) -> None:
    logs_dir = tmp_path / "logs"
    handler = logging.StreamHandler(io.StringIO())

    log.init(handler=handler, logs_dir=logs_dir)

    assert logs_dir.is_dir()
    assert isolated_root_logger.level == logging.INFO
    assert handler in isolated_root_logger.handlers


def test_init_emits_timestamp_source_and_public_metadata(
    tmp_path: Path,
    isolated_root_logger: logging.Logger,
) -> None:
    logs_dir = tmp_path / "logs"

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)

    log.init(handler=handler, logs_dir=logs_dir)

    logger = logging.getLogger("core.log.test")
    assert handler in isolated_root_logger.handlers
    current_frame = inspect.currentframe()
    assert current_frame is not None
    log_call_line = current_frame.f_lineno + 1
    logger.info(
        "hello",
        extra={
            "_private": "hidden",
            "count": 3,
            "user": "테스터",
            "value": _StringableValue(),
        },
    )
    handler.flush()

    log_line = stream.getvalue().strip()
    prefix, metadata_json = log_line.split(" | ", maxsplit=1)
    timestamp, level_name, logger_name, message = prefix.split(" ", maxsplit=3)

    parsed_timestamp = datetime.datetime.fromisoformat(timestamp)
    assert parsed_timestamp.tzinfo is not None
    assert parsed_timestamp.microsecond % 1000 == 0
    assert level_name == "INFO"
    assert logger_name == "core.log.test"
    assert message == "hello"
    assert json.loads(metadata_json) == {
        "count": 3,
        "source": f"{Path(__file__).resolve()}:{log_call_line}",
        "user": "테스터",
        "value": "stringable",
    }
