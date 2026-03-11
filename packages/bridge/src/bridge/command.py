import asyncio
import logging
import queue
import threading
from contextlib import suppress
from dataclasses import dataclass, field

Command = str | None


@dataclass(kw_only=True)
class AsyncCompletion:
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[None]


@dataclass(kw_only=True)
class SyncCompletion:
    done: threading.Event = field(default_factory=threading.Event)
    error: Exception | None = None


@dataclass(kw_only=True)
class Request:
    command: Command
    completion: AsyncCompletion | SyncCompletion


def _enqueue_sync(
    request_queue: queue.Queue[Request],
    command: Command,
) -> SyncCompletion:
    completion = SyncCompletion()
    request_queue.put_nowait(Request(command=command, completion=completion))
    return completion


def _wait_sync(completion: SyncCompletion) -> None:
    completion.done.wait()
    if completion.error is not None:
        raise completion.error


def _resolve_async(completion: AsyncCompletion, error: Exception | None) -> None:
    def resolve() -> None:
        if completion.future.done():
            return

        if error is not None:
            completion.future.set_exception(error)
        else:
            completion.future.set_result(None)

    # Event loop was already closed by the caller.
    with suppress(RuntimeError):
        completion.loop.call_soon_threadsafe(resolve)


def _check_running(*, running: bool) -> None:
    if not running:
        raise RuntimeError(
            "Command runner is not running.",
        )


class Context:
    def __init__(self) -> None:
        self.queue = queue.Queue[Request]()
        self.thread = threading.Thread(
            name="game_command_thread",
            target=_main,
            args=(self.queue,),
        )
        self.running = False
        self.lock = threading.Lock()


def _main(request_queue: queue.Queue[Request]) -> None:
    logger = logging.getLogger(f"{__name__}.thread")
    logger.info("Started.")

    while True:
        request = request_queue.get()
        error: Exception | None = None

        try:
            if request.command is None:
                break
            print(request.command, flush=True)  # noqa: T201
        except Exception as e:  # noqa: BLE001
            error = e
        finally:
            if isinstance(request.completion, AsyncCompletion):
                _resolve_async(request.completion, error)
            else:
                if error is not None:
                    request.completion.error = error
                request.completion.done.set()

    logger.info("Exited.")


class Writer:
    def __init__(self, context: Context) -> None:
        self._context = context

    def write_sync(self, command: str) -> None:
        with self._context.lock:
            _check_running(running=self._context.running)
            completion = _enqueue_sync(self._context.queue, command)

        _wait_sync(completion)

    async def write(self, command: str) -> None:
        with self._context.lock:
            _check_running(running=self._context.running)
            loop = asyncio.get_running_loop()
            future: asyncio.Future[None] = loop.create_future()
            completion = AsyncCompletion(loop=loop, future=future)
            self._context.queue.put_nowait(
                Request(command=command, completion=completion),
            )

        await future


class ThreadRunner:
    def __init__(self) -> None:
        self._context = Context()

    def start(self) -> None:
        with self._context.lock:
            if self._context.running:
                raise RuntimeError(
                    "Command runner is already running.",
                )

            self._context.thread.start()
            self._context.running = True

    def stop(self) -> None:
        with self._context.lock:
            _check_running(running=self._context.running)
            completion = _enqueue_sync(self._context.queue, None)
            self._context.running = False

        _wait_sync(completion)
        self._context.thread.join()

    def writer(self) -> Writer:
        return Writer(self._context)
