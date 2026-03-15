import inspect
import json
import logging
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest
from bridge import log

EXPECTED_BACKUP_COUNT = 5


@pytest.fixture
def isolated_root_logger() -> Iterator[logging.Logger]:
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers.copy()
    original_level = root_logger.level

    try:
        yield root_logger
    finally:
        root_logger.setLevel(original_level)
        for handler in root_logger.handlers.copy():
            if handler in original_handlers:
                continue

            root_logger.removeHandler(handler)
            handler.close()


def test_init_creates_rotating_file_handler_and_writes_logs(
    isolated_root_logger: logging.Logger,
    tmp_path: Path,
) -> None:
    log_file = tmp_path / "logs" / "bridge.log"
    original_handlers = isolated_root_logger.handlers.copy()

    log.init(log_file=log_file)

    assert log_file.parent.is_dir()
    assert isolated_root_logger.level == logging.INFO
    added_handlers = [
        handler
        for handler in isolated_root_logger.handlers
        if handler not in original_handlers
    ]
    assert len(added_handlers) == 1

    handler = added_handlers[0]
    assert isinstance(handler, RotatingFileHandler)
    assert Path(handler.baseFilename) == log_file
    assert handler.maxBytes == 10 * 1024 * 1024
    assert handler.backupCount == EXPECTED_BACKUP_COUNT
    assert handler.encoding == "utf-8"

    logger = logging.getLogger("bridge.log.test")
    current_frame = inspect.currentframe()
    assert current_frame is not None
    log_call_line = current_frame.f_lineno + 1
    logger.info("hello", extra={"request_id": "abc123"})
    handler.flush()

    log_line = log_file.read_text(encoding="utf-8").strip()
    prefix, metadata_json = log_line.split(" | ", maxsplit=1)
    timestamp, level_name, logger_name, message = prefix.split(" ", maxsplit=3)

    assert timestamp
    assert level_name == "INFO"
    assert logger_name == "bridge.log.test"
    assert message == "hello"
    assert json.loads(metadata_json) == {
        "request_id": "abc123",
        "source": f"{Path(__file__).resolve()}:{log_call_line}",
    }
