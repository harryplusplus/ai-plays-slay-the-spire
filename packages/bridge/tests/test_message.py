import asyncio
import io

from bridge import message_thread


def drain_loop(loop: asyncio.AbstractEventLoop) -> None:
    loop.run_until_complete(asyncio.sleep(0))


def test_run_enqueues_stripped_messages_and_eof() -> None:
    input_ = io.StringIO("play\nstate\n")
    loop = asyncio.new_event_loop()
    queue: asyncio.Queue[message_thread.RawMessage] = asyncio.Queue()

    try:
        message_thread._run(input_, loop, queue)
        drain_loop(loop)

        assert queue.get_nowait() == "play"
        assert queue.get_nowait() == "state"
        assert queue.get_nowait() is None
    finally:
        loop.close()


def test_run_stops_when_loop_is_closed() -> None:
    input_ = io.StringIO("play\n")
    loop = asyncio.new_event_loop()
    loop.close()
    queue: asyncio.Queue[message_thread.RawMessage] = asyncio.Queue()

    message_thread._run(input_, loop, queue)

    assert queue.empty() is True


def test_start_creates_daemon_thread_and_runs_message_loop() -> None:
    input_ = io.StringIO("")
    loop = asyncio.new_event_loop()
    queue: asyncio.Queue[message_thread.RawMessage] = asyncio.Queue()

    try:
        thread = message_thread.start(input_, loop, queue)
        thread.join(timeout=1)
        drain_loop(loop)

        assert thread.is_alive() is False
        assert thread.daemon is True
        assert queue.get_nowait() is None
    finally:
        loop.close()
