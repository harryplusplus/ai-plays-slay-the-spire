import logging
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest
from bridge import log

BACKUP_COUNT = 5
MAX_BYTES = 10 * 1024 * 1024


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


def test_init_creates_parent_directory_and_adds_rotating_file_handler(
    tmp_path: Path,
    isolated_root_logger: logging.Logger,
) -> None:
    log_file = tmp_path / "nested" / "bridge.log"

    log.init(log_file=log_file)

    handlers = [
        handler
        for handler in isolated_root_logger.handlers
        if isinstance(handler, RotatingFileHandler)
    ]

    assert log_file.parent.exists() is True
    assert len(handlers) == 1

    handler = handlers[0]
    assert Path(handler.baseFilename) == log_file
    assert handler.maxBytes == MAX_BYTES
    assert handler.backupCount == BACKUP_COUNT
    assert handler.encoding == "utf-8"
