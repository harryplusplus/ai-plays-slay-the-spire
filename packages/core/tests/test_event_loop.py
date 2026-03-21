import asyncio

import pytest
from core import event_loop


def raise_in_current_thread_loop(loops: list[asyncio.AbstractEventLoop]) -> None:
    with event_loop.current_thread_loop() as loop:
        loops.append(loop)
        raise RuntimeError("boom")


def test_current_thread_loop_sets_current_loop_and_closes_on_exit() -> None:
    with event_loop.current_thread_loop() as loop:
        assert asyncio.get_event_loop() is loop
        assert loop.run_until_complete(asyncio.sleep(0, result=1)) == 1
        assert loop.is_closed() is False

    assert loop.is_closed() is True


def test_current_thread_loop_creates_distinct_loops() -> None:
    with event_loop.current_thread_loop() as first_loop:
        pass

    with event_loop.current_thread_loop() as second_loop:
        pass

    assert first_loop is not second_loop
    assert first_loop.is_closed() is True
    assert second_loop.is_closed() is True


def test_current_thread_loop_closes_loop_when_body_raises() -> None:
    loops: list[asyncio.AbstractEventLoop] = []

    with pytest.raises(RuntimeError, match="boom"):
        raise_in_current_thread_loop(loops)

    assert len(loops) == 1
    assert loops[0].is_closed() is True
