import asyncio
import logging

import uvicorn

from bridge import log
from bridge.api import app
from bridge.bridge import Bridge

logger = logging.getLogger(__name__)


async def _main() -> None:
    config = uvicorn.Config(app, access_log=False, log_config=None)
    server = uvicorn.Server(config)
    bridge = Bridge(server)
    app.state.bridge = bridge

    await bridge.start()
    await bridge.execute("ready")
    try:
        await server.serve()
    finally:
        await bridge.close()


def main() -> None:
    log.init()
    logger.info("Started.")
    asyncio.run(_main())
    logger.info("Exited.")


if __name__ == "__main__":
    main()
