import asyncio
import io

import pytest
from bridge import message


def drain_loop(loop: asyncio.AbstractEventLoop) -> None:
    loop.run_until_complete(asyncio.sleep(0))


def test_to_async_queue_put_nowait_enqueues_items() -> None:
    loop = asyncio.new_event_loop()
    queue = message.Queue()
    try:
        async_queue = message.ToAsyncQueue(loop, queue)

        async_queue.put_nowait("play")
        drain_loop(loop)

        assert queue.get_nowait() == "play"
    finally:
        loop.close()


def test_to_async_queue_put_nowait_raises_closed_error_for_closed_loop() -> None:
    loop = asyncio.new_event_loop()
    loop.close()
    queue = message.Queue()
    async_queue = message.ToAsyncQueue(loop, queue)

    with pytest.raises(message.ClosedError):
        async_queue.put_nowait("play")

    assert queue.empty() is True


def test_process_next_enqueues_stripped_line() -> None:
    input_ = io.StringIO("play\n")
    loop = asyncio.new_event_loop()
    queue = message.Queue()
    try:
        async_queue = message.ToAsyncQueue(loop, queue)

        should_continue = message.process_next(input_, async_queue)
        drain_loop(loop)

        assert should_continue is True
        assert queue.get_nowait() == "play"
    finally:
        loop.close()


def test_process_next_returns_false_at_eof() -> None:
    input_ = io.StringIO("")
    loop = asyncio.new_event_loop()
    queue = message.Queue()
    try:
        async_queue = message.ToAsyncQueue(loop, queue)

        should_continue = message.process_next(input_, async_queue)

        assert should_continue is False
        assert queue.empty() is True
    finally:
        loop.close()


def test_process_next_returns_false_when_queue_is_closed() -> None:
    input_ = io.StringIO("play\n")
    loop = asyncio.new_event_loop()
    loop.close()
    queue = message.Queue()
    async_queue = message.ToAsyncQueue(loop, queue)

    should_continue = message.process_next(input_, async_queue)

    assert should_continue is False
    assert queue.empty() is True


def test_run_forwards_messages_and_enqueues_eof() -> None:
    input_ = io.StringIO("play\nstate\n")
    loop = asyncio.new_event_loop()
    queue = message.Queue()
    try:
        async_queue = message.ToAsyncQueue(loop, queue)

        message.run(input_, async_queue)
        drain_loop(loop)

        assert queue.get_nowait() == "play"
        assert queue.get_nowait() == "state"
        assert queue.get_nowait() is None
    finally:
        loop.close()


def test_run_suppresses_closed_error_when_eof_signal_cannot_be_enqueued() -> None:
    input_ = io.StringIO("")
    loop = asyncio.new_event_loop()
    loop.close()
    queue = message.Queue()
    async_queue = message.ToAsyncQueue(loop, queue)

    message.run(input_, async_queue)

    assert queue.empty() is True


def test_start_thread_starts_and_finishes_daemon_thread() -> None:
    input_ = io.StringIO("")
    loop = asyncio.new_event_loop()
    queue = message.Queue()
    try:
        async_queue = message.ToAsyncQueue(loop, queue)

        thread = message.start_thread(input_, async_queue)
        thread.join(timeout=1)
        drain_loop(loop)

        assert thread.is_alive() is False
        assert thread.daemon is True
        assert queue.get_nowait() is None
    finally:
        loop.close()
