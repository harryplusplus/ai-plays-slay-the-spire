from logging.handlers import RotatingFileHandler
from pathlib import Path

from core import log
from core.paths import BRIDGE_LOG_FILE


def init(*, log_file: Path = BRIDGE_LOG_FILE) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    log.init(handler=handler)
