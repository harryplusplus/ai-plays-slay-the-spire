import logging
from pathlib import Path

from common.log import create_local_json_formatter, create_rotating_file_handler


def init_logger() -> None:
    handler = create_rotating_file_handler(
        Path.home() / ".sts" / "logs" / "bridge.jsonl"
    )
    handler.setFormatter(create_local_json_formatter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
