import datetime
import logging
import sys


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

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_add_timestamp)

    formatter = logging.Formatter(
        "%(timestamp)s %(levelname)s [%(name)s][%(threadName)s][%(pathname)s:%(lineno)d] %(message)s",
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
