from core.paths import DB_SQLITE_FILE

from sts import log
from sts.app import Config, app


def main() -> None:
    log.init()
    app(obj=Config(sqlite_file=DB_SQLITE_FILE))
