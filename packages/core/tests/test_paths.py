from pathlib import Path

from core import paths


def test_paths_are_derived_from_root_dir() -> None:
    root_dir = Path(__file__).resolve().parents[3]

    assert root_dir == paths.ROOT_DIR
    assert root_dir / ".work" == paths.WORK_DIR
    assert root_dir / "agent" == paths.AGENT_DIR
    assert paths.LOGS_DIR == paths.WORK_DIR / "logs"
    assert paths.BRIDGE_LOG_FILE == paths.LOGS_DIR / "bridge.log"
    assert paths.CODEX_DIR == paths.WORK_DIR / "codex"
    assert paths.SESSIONS_DIR == paths.CODEX_DIR / "sessions"
    assert paths.OUTPUT_SCHEMA_FILE == paths.WORK_DIR / "output_schema.json"
    assert paths.OUTPUT_LAST_MESSAGE_FILE == paths.WORK_DIR / "output_last_message.json"
    assert Path.home() / ".codex" / "auth.json" == paths.USER_AUTH_JSON_FILE
    assert paths.DB_SQLITE_FILE == paths.WORK_DIR / "db.sqlite"
