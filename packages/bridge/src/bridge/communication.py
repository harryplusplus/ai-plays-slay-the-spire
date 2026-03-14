import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TextIO


class Communicator:
    def __init__(self, in_: TextIO | None = None, out: TextIO | None = None) -> None:
        self._in = in_ if in_ is not None else sys.stdin
        self._out = out if out is not None else sys.stdout

    def communicate(self, command: str) -> str:
        self._out.write(f"{command}\n")
        self._out.flush()
        line = self._in.readline()
        if line == "":
            raise RuntimeError("Unexpected EOF from stdin.")
        return line.rstrip()


class Orchestrator:
    def __init__(self, communicator: Communicator | None = None) -> None:
        self._communicator = (
            communicator if communicator is not None else Communicator()
        )
        self._communicating = False
        self._lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1)

    def close(self) -> None:
        self._executor.shutdown()

    async def communicate(self, command: str) -> str:
        async with self._lock:
            if self._communicating:
                raise RuntimeError("Already communicating.")
            self._communicating = True

        try:
            return await asyncio.get_running_loop().run_in_executor(
                self._executor,
                self._communicator.communicate,
                command,
            )
        finally:
            async with self._lock:
                self._communicating = False
