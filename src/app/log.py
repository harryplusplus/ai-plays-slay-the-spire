import logging
from logging.handlers import RotatingFileHandler

from app.paths import LOG_DIR, LOG_FILE


def init() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    LOG_DIR.mkdir(exist_ok=True, parents=True)
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)

    root.addHandler(handler)
