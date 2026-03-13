import asyncio
import logging
import signal

import uvicorn

from bridge import log
from bridge.api import app
from bridge.bridge import Bridge

logger = logging.getLogger(__name__)


def on_signal(*_, **__):
    logger.info("AAAA")


async def _main() -> None:
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    config = uvicorn.Config(app, access_log=False, log_config=None)
    server = uvicorn.Server(config)
    bridge = Bridge(server)
    app.state.bridge = bridge

    try:
        await bridge.start()
        await bridge.execute("ready")
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
