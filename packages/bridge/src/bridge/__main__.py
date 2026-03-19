import asyncio
import logging

from core import db
from core.paths import DB_SQLITE_FILE

from bridge import log

logger = logging.getLogger(__name__)


async def main(engine: db.AsyncEngine) -> None:
    try:
        await db.init(engine)
        await db.init_dev(engine)
    finally:
        await db.close_engine(engine)


if __name__ == "__main__":
    log.init()
    logger.info("Bridge started.")
    engine = db.create_engine(DB_SQLITE_FILE)
    asyncio.run(main(engine))
    logger.info("Bridge closed.")
