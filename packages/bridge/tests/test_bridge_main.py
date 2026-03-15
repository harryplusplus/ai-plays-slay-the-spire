import runpy
import sys
from unittest.mock import Mock, call, patch

from bridge import __main__ as bridge_main
from bridge.api import app


def test_main_initializes_logging_runs_uvicorn_and_logs_lifecycle() -> None:
    with (
        patch("bridge.__main__.log.init") as log_init,
        patch("bridge.__main__.uvicorn.run") as uvicorn_run,
        patch("bridge.__main__.logger.info") as logger_info,
    ):
        bridge_main.main()

    log_init.assert_called_once_with()
    uvicorn_run.assert_called_once_with(app, log_config=None)
    assert logger_info.call_args_list == [call("Started."), call("Exited.")]


def test_module_runs_main_when_executed_as_script() -> None:
    logger = Mock()
    sys.modules.pop("bridge.__main__", None)

    with (
        patch("bridge.log.init") as log_init,
        patch("uvicorn.run") as uvicorn_run,
        patch("logging.getLogger", return_value=logger),
    ):
        runpy.run_module("bridge.__main__", run_name="__main__")

    log_init.assert_called_once_with()
    uvicorn_run.assert_called_once()
    assert logger.info.call_args_list == [call("Started."), call("Exited.")]
