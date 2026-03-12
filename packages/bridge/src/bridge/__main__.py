import asyncio
import logging

from bridge import api, command, log, message
from bridge.common import CommandQueue, MessageQueue, Sentinel

logger = logging.getLogger(__name__)


def main() -> None:
    log.init()
    logger.info("Started.")

    loop = asyncio.new_event_loop()
    message_queue = MessageQueue()
    command_queue = CommandQueue()

    message_thread = message.create_thread(loop, message_queue)
    command_thread = command.create_thread(loop, command_queue)
    server, api_thread = api.create_thread(
        loop,
        message_queue,
        command_queue,
    )

    message_thread.start()
    command_thread.start()
    api_thread.start()

    message_thread.join()

    server.should_exit = True
    api_thread.join()

    command_queue.put(Sentinel())
    command_thread.join()

    logger.info("Exited.")


if __name__ == "__main__":
    main()
