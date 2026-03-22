from core.paths import DB_SQLITE

from sts import log
from sts.app import Config, app


def main() -> None:
    log.init()
    app(obj=Config(sqlite_file=DB_SQLITE))
