import logging

from bridge import api, command, log, message

logger = logging.getLogger(__name__)


def main() -> None:
    log.init()
    logger.info("Started.")

    command_runner = command.ThreadRunner()
    message_runner = message.Runner(command_runner.writer())
    api_runner = api.ThreadRunner(message_runner.accessor(), command_runner.writer())

    command_runner.start()
    api_runner.start()

    message_runner.run()

    api_runner.stop()
    command_runner.stop()

    logger.info("Exited.")


if __name__ == "__main__":
    main()
