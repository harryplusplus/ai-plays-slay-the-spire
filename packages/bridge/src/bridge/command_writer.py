import sys
from typing import TextIO


class CommandWriter:
    def __init__(
        self,
        output: TextIO | None = None,
    ) -> None:
        self._output = output if output is not None else sys.stdout

    def write(self, command: str) -> None:
        self._output.write(f"{command}\n")
        self._output.flush()
