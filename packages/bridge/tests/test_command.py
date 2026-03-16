import io
from contextlib import redirect_stdout

import pytest
from bridge.command import CommandSenderServiceImpl, CommandWriter


def test_writer_writes_command_with_trailing_newline() -> None:
    out = io.StringIO()
    command_writer = CommandWriter(out)

    command_writer("play")

    assert out.getvalue() == "play\n"


def test_writer_uses_stdout_when_output_is_not_provided() -> None:
    out = io.StringIO()

    with redirect_stdout(out):
        command_writer = CommandWriter()
        command_writer("ready")

    assert out.getvalue() == "ready\n"


@pytest.mark.anyio
async def test_threaded_sender_service_sends_with_injected_writer() -> None:
    out = io.StringIO()
    command_sender_service = CommandSenderServiceImpl(CommandWriter(out))

    try:
        await command_sender_service.command_sender()("play")
    finally:
        command_sender_service.close()

    assert out.getvalue() == "play\n"


@pytest.mark.anyio
async def test_threaded_sender_service_uses_stdout_when_writer_is_not_provided() -> (
    None
):
    out = io.StringIO()

    with redirect_stdout(out):
        command_sender_service = CommandSenderServiceImpl()
        try:
            await command_sender_service.command_sender()("ready")
        finally:
            command_sender_service.close()

    assert out.getvalue() == "ready\n"
