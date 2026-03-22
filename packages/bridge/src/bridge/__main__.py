import asyncio
import logging
import sys
from contextlib import suppress

import uvicorn

from bridge import log, message
from bridge.app import app
from bridge.container import Container

logger = logging.getLogger(__name__)


def main() -> None:
    log.init()
    logger.info("Bridge started.")

    with asyncio.Runner() as runner:
        loop = runner.get_loop()
        message_queue = message.Queue()
        message.start_thread(sys.stdin, message.ToAsyncQueue(loop, message_queue))

        container = Container(message_queue)
        container.attach(app)

        config = uvicorn.Config(app, log_config=None, use_colors=False)
        server = uvicorn.Server(config)
        with suppress(KeyboardInterrupt):
            runner.run(server.serve())

    logger.info("Bridge closed.")


if __name__ == "__main__":
    main()
