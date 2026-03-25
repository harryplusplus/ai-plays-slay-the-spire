import sys
from typing import Protocol, TextIO

from typing_extensions import override


class CommandWriter(Protocol):
    def write(self, command: str) -> None: ...


class CommandWriterImpl(CommandWriter):
    def __init__(
        self,
        output: TextIO | None = None,
    ) -> None:
        self._output = output if output is not None else sys.stdout

    @override
    def write(self, command: str) -> None:
        self._output.write(f"{command}\n")
        self._output.flush()
