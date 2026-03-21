from sts import log
from sts.app import app


def main() -> None:
    log.init()
    app()
