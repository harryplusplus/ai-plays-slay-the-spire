import io

import pytest
from bridge.command import CommandSenderServiceImpl, CommandWriter


def test_writer_writes_command_with_trailing_newline() -> None:
    out = io.StringIO()
    command_writer = CommandWriter(out)

    command_writer("play")

    assert out.getvalue() == "play\n"


@pytest.mark.anyio
async def test_threaded_sender_service_sends_with_injected_writer() -> None:
    out = io.StringIO()
    command_sender_service = CommandSenderServiceImpl(CommandWriter(out))

    try:
        await command_sender_service.command_sender()("play")
    finally:
        command_sender_service.close()

    assert out.getvalue() == "play\n"
