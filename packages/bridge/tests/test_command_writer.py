import io
from contextlib import redirect_stdout

from bridge.command_writer import CommandWriter
from typing_extensions import override


class RecordingOutput(io.StringIO):
    flush_count: int

    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    @override
    def flush(self) -> None:
        super().flush()
        self.flush_count += 1


def test_write_appends_newline_and_flushes_injected_output() -> None:
    output = RecordingOutput()
    writer = CommandWriter(output)

    writer.write("play")

    assert output.getvalue() == "play\n"
    assert output.flush_count == 1


def test_write_uses_stdout_when_output_is_none() -> None:
    output = RecordingOutput()

    with redirect_stdout(output):
        writer = CommandWriter()
        writer.write("state")

    assert output.getvalue() == "state\n"
    assert output.flush_count == 1
