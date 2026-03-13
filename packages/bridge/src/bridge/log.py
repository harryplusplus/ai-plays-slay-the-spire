import datetime
import logging
from logging.handlers import RotatingFileHandler

from core.paths import BRIDGE_LOG_FILE, LOGS_DIR


def _add_timestamp(record: logging.LogRecord) -> bool:
    record.timestamp = (
        datetime.datetime.fromtimestamp(record.created)
        .astimezone()
        .isoformat(timespec="milliseconds")
    )
    return True


def init() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    LOGS_DIR.mkdir(exist_ok=True, parents=True)

    handler = RotatingFileHandler(
        BRIDGE_LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.addFilter(_add_timestamp)

    formatter = logging.Formatter(
        "%(timestamp)s %(levelname)s [%(name)s] %(message)s\n"
        "  at %(pathname)s:%(lineno)d",
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
