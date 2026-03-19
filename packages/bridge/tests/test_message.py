import io
from collections.abc import Callable

from bridge import message


class ImmediateLoop:
    calls: list[tuple[Callable[..., object], tuple[object, ...]]]

    def __init__(self) -> None:
        self.calls = []

    def call_soon_threadsafe(
        self,
        callback: Callable[..., object],
        *args: object,
    ) -> object:
        self.calls.append((callback, args))
        return callback(*args)


class ClosedLoop:
    def call_soon_threadsafe(
        self,
        callback: Callable[..., object],
        *args: object,
    ) -> object:
        del callback, args
        raise RuntimeError("Event loop is closed")


def test_forward_next_message_enqueues_stripped_line() -> None:
    input_stream = io.StringIO("play\n")
    loop = ImmediateLoop()
    queue = message.MessageQueue()

    should_continue = message.forward_next_message(input_stream, loop, queue)

    assert should_continue is True
    assert queue.get_nowait() == "play"


def test_forward_next_message_returns_false_at_eof() -> None:
    input_stream = io.StringIO("")
    loop = ImmediateLoop()
    queue = message.MessageQueue()

    should_continue = message.forward_next_message(input_stream, loop, queue)

    assert should_continue is False
    assert queue.empty() is True


def test_forward_next_message_returns_false_when_loop_is_closed() -> None:
    input_stream = io.StringIO("play\n")
    loop = ClosedLoop()
    queue = message.MessageQueue()

    should_continue = message.forward_next_message(input_stream, loop, queue)

    assert should_continue is False
    assert queue.empty() is True


def test_run_message_thread_forwards_messages_and_enqueues_eof() -> None:
    input_stream = io.StringIO("play\nstate\n")
    loop = ImmediateLoop()
    queue = message.MessageQueue()

    message.run_message_thread(input_stream, loop, queue)

    assert queue.get_nowait() == "play"
    assert queue.get_nowait() == "state"
    assert queue.get_nowait() is None


def test_run_message_thread_suppresses_closed_loop_on_eof() -> None:
    input_stream = io.StringIO("")
    loop = ClosedLoop()
    queue = message.MessageQueue()

    message.run_message_thread(input_stream, loop, queue)

    assert queue.empty() is True


def test_start_message_thread_starts_and_finishes_thread() -> None:
    input_stream = io.StringIO("")
    loop = ImmediateLoop()
    queue = message.MessageQueue()

    thread = message.start_message_thread(input_stream, loop, queue)
    thread.join(timeout=1)

    assert thread.is_alive() is False
    assert thread.daemon is True
    assert queue.get_nowait() is None
