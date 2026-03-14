import datetime
import json
import logging

from core.paths import LOGS_DIR


def _add_timestamp(record: logging.LogRecord) -> bool:
    record.timestamp = (
        datetime.datetime.fromtimestamp(record.created)
        .astimezone()
        .isoformat(timespec="milliseconds")
    )
    return True


def _add_source(record: logging.LogRecord) -> bool:
    record.source = f"{record.pathname}:{record.lineno}"
    return True


RESERVED_LOG_RECORD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "timestamp",
    "color_message",
    "websocket",
}


def _add_metadata_json(record: logging.LogRecord) -> bool:
    metadata = {}
    for key, value in record.__dict__.items():
        if key in RESERVED_LOG_RECORD_ATTRS or key.startswith("_"):
            continue
        metadata[key] = value

    record.metadata_json = json.dumps(metadata, ensure_ascii=False, default=str)
    return True


def init(*, handler: logging.Handler) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    LOGS_DIR.mkdir(exist_ok=True, parents=True)

    handler.addFilter(_add_timestamp)
    handler.addFilter(_add_source)
    handler.addFilter(_add_metadata_json)

    formatter = logging.Formatter(
        "%(timestamp)s %(levelname)s %(name)s %(message)s | %(metadata_json)s",
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
