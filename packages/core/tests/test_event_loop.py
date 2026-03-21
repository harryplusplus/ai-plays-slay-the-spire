import asyncio

import pytest
from core import event_loop


def raise_in_scoped_event_loop(loops: list[asyncio.AbstractEventLoop]) -> None:
    with event_loop.scoped() as loop:
        loops.append(loop)
        raise RuntimeError("boom")


def test_scoped_sets_current_loop_and_closes_on_exit() -> None:
    with event_loop.scoped() as loop:
        assert asyncio.get_event_loop() is loop
        assert loop.run_until_complete(asyncio.sleep(0, result=1)) == 1
        assert loop.is_closed() is False

    assert loop.is_closed() is True


def test_scoped_creates_distinct_loops() -> None:
    with event_loop.scoped() as first_loop:
        pass

    with event_loop.scoped() as second_loop:
        pass

    assert first_loop is not second_loop
    assert first_loop.is_closed() is True
    assert second_loop.is_closed() is True


def test_scoped_restores_previous_loop_on_exit() -> None:
    previous = asyncio.new_event_loop()
    asyncio.set_event_loop(previous)

    try:
        with event_loop.scoped(previous=previous) as loop:
            assert asyncio.get_event_loop() is loop

        assert asyncio.get_event_loop() is previous
    finally:
        asyncio.set_event_loop(None)
        previous.close()


def test_nested_scoped_restores_outer_loop() -> None:
    with event_loop.scoped() as outer_loop:
        with event_loop.scoped(previous=outer_loop) as inner_loop:
            assert asyncio.get_event_loop() is inner_loop

        assert asyncio.get_event_loop() is outer_loop


def test_scoped_closes_loop_when_body_raises() -> None:
    loops: list[asyncio.AbstractEventLoop] = []

    with pytest.raises(RuntimeError, match="boom"):
        raise_in_scoped_event_loop(loops)

    assert len(loops) == 1
    assert loops[0].is_closed() is True
