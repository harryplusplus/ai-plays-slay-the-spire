import asyncio
import logging
import sys
from contextlib import suppress

import uvicorn

from bridge import log, message_thread
from bridge.api import create_app
from bridge.container import Container

logger = logging.getLogger(__name__)


def main() -> None:
    log.init()
    logger.info("Bridge started.")

    with asyncio.Runner() as runner:
        loop = runner.get_loop()
        message_queue = asyncio.Queue[message_thread.RawMessage]()
        message_thread.start(sys.stdin, loop, message_queue)

        container = Container(message_queue)
        app = create_app(container)
        config = uvicorn.Config(app, log_config=None, use_colors=False)
        server = uvicorn.Server(config)
        with suppress(KeyboardInterrupt):
            runner.run(server.serve())

    logger.info("Bridge closed.")


if __name__ == "__main__":
    main()
