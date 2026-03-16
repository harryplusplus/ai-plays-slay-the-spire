import asyncio
import io
import logging
import sys

import pytest
from bridge.message import MessageReader, MessageReceiverServiceImpl

EXPECTED_MESSAGE_COUNT = 2


def test_reader_returns_stripped_line_from_injected_input() -> None:
    message_reader = MessageReader(io.StringIO("hello\n"))

    assert message_reader() == "hello"


def test_reader_raises_eof_error_when_input_reaches_eof() -> None:
    message_reader = MessageReader(io.StringIO(""))

    with pytest.raises(EOFError, match=r"MessageReader reached EOF\."):
        message_reader()


def test_reader_uses_stdin_when_input_is_not_provided() -> None:
    original_stdin = sys.stdin
    sys.stdin = io.StringIO("ready\n")

    try:
        message_reader = MessageReader()
        assert message_reader() == "ready"
    finally:
        sys.stdin = original_stdin


@pytest.mark.anyio
async def test_threaded_receiver_service_reads_messages_until_eof(
    caplog: pytest.LogCaptureFixture,
) -> None:
    received_messages: list[str] = []
    received_all_messages = asyncio.Event()

    async def message_handler(message: str) -> None:
        received_messages.append(message)
        if len(received_messages) == EXPECTED_MESSAGE_COUNT:
            received_all_messages.set()

    message_receiver_service = MessageReceiverServiceImpl(
        message_handler=message_handler,
        message_reader=MessageReader(io.StringIO("first\nsecond\n")),
    )

    with caplog.at_level(logging.INFO, logger="bridge.message"):
        message_receiver_service.start()
        await asyncio.wait_for(received_all_messages.wait(), timeout=1)
        await asyncio.sleep(0)

    assert received_messages == ["first", "second"]
    assert "Stopping loop due to EOFError." in caplog.text


@pytest.mark.anyio
async def test_threaded_receiver_service_logs_handler_exceptions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    handler_started = asyncio.Event()

    async def message_handler(message: str) -> None:
        assert message == "boom"
        handler_started.set()
        raise RuntimeError("boom")

    message_receiver_service = MessageReceiverServiceImpl(
        message_handler=message_handler,
        message_reader=MessageReader(io.StringIO("boom\n")),
    )

    with caplog.at_level(logging.ERROR, logger="bridge.message"):
        message_receiver_service.start()
        await asyncio.wait_for(handler_started.wait(), timeout=1)
        await asyncio.sleep(0)

    assert "Error sending message to connection." in caplog.text
