import logging
import sys

from core import log


def init() -> None:
    handler = logging.StreamHandler(sys.stdout)
    log.init(handler=handler)
