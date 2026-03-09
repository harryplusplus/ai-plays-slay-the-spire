class GameMessageWriter:
    def _write(self, msg: str) -> None:
        print(msg, flush=True)

    def ready(self) -> None:
        self._write("ready")
