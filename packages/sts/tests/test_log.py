import logging
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest
from sts import log

EXPECTED_BACKUP_COUNT = 5


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
    isolated_root_logger: logging.Logger,
    tmp_path: Path,
) -> None:
    log_file = tmp_path / "logs" / "sts.log"

    assert not log_file.parent.exists()

    log.init(log_file=log_file)

    assert log_file.parent.is_dir()
    assert log_file.is_file()

    matching_handlers = [
        handler
        for handler in isolated_root_logger.handlers
        if isinstance(handler, RotatingFileHandler)
    ]

    assert len(matching_handlers) == 1

    handler = matching_handlers[0]

    assert isinstance(handler, RotatingFileHandler)
    assert handler.baseFilename == str(log_file)
    assert handler.maxBytes == 10 * 1024 * 1024
    assert handler.backupCount == EXPECTED_BACKUP_COUNT
    assert handler.encoding == "utf-8"
