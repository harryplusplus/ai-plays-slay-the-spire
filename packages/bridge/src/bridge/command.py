import asyncio
import logging
import threading

from bridge.common import Command, CommandQueue, Sentinel

logger = logging.getLogger(__name__)


def _execute(command: str) -> None:
    print(command, flush=True)  # noqa: T201


def _resolve(
    loop: asyncio.AbstractEventLoop,
    command: Command,
    exception: Exception | None,
) -> None:
    def resolve() -> None:
        if command.future.done():
            return

        if exception is not None:
            command.future.set_exception(exception)
        else:
            command.future.set_result(None)

    loop.call_soon_threadsafe(resolve)


def _main(loop: asyncio.AbstractEventLoop, command_queue: CommandQueue) -> None:
    logger.info("Started.")

    while True:
        command = command_queue.get()
        if isinstance(command, Sentinel):
            break

        exception: Exception | None = None
        try:
            _execute(command.command)
        except Exception as e:  # noqa: BLE001
            exception = e
        finally:
            _resolve(loop, command, exception)

    logger.info("Exited.")


def create_thread(
    loop: asyncio.AbstractEventLoop,
    command_queue: CommandQueue,
) -> threading.Thread:
    return threading.Thread(
        name="command_thread",
        target=_main,
        args=(loop, command_queue),
    )
