from logging.handlers import RotatingFileHandler

from core import log
from core.paths import BRIDGE_LOG_FILE


def init() -> None:
    handler = RotatingFileHandler(
        BRIDGE_LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    log.init(handler=handler)
