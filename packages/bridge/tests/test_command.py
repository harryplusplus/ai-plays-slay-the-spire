import io
from contextlib import redirect_stdout

import pytest
from bridge import command


def test_writer_writes_command_with_trailing_newline() -> None:
    out = io.StringIO()
    writer = command.Writer(out)

    writer("play")

    assert out.getvalue() == "play\n"


def test_writer_uses_stdout_when_output_is_not_provided() -> None:
    out = io.StringIO()

    with redirect_stdout(out):
        writer = command.Writer()
        writer("ready")

    assert out.getvalue() == "ready\n"


@pytest.mark.anyio
async def test_threaded_sender_service_sends_with_injected_writer() -> None:
    out = io.StringIO()
    threaded_sender = command.ThreadedSenderService(command.Writer(out))

    try:
        await threaded_sender.sender()("play")
    finally:
        threaded_sender.close()

    assert out.getvalue() == "play\n"


@pytest.mark.anyio
async def test_threaded_sender_service_uses_stdout_when_writer_is_not_provided() -> (
    None
):
    out = io.StringIO()

    with redirect_stdout(out):
        threaded_sender = command.ThreadedSenderService()
        try:
            await threaded_sender.sender()("ready")
        finally:
            threaded_sender.close()

    assert out.getvalue() == "ready\n"
