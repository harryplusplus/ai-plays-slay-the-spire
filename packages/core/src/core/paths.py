from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
WORK_DIR = ROOT_DIR / ".work"
AGENT_DIR = ROOT_DIR / "agent"

LOGS_DIR = WORK_DIR / "logs"
BRIDGE_LOG_FILE = LOGS_DIR / "bridge.log"
STS_LOG_FILE = LOGS_DIR / "sts.log"

CODEX_DIR = WORK_DIR / "codex"
SESSIONS_DIR = CODEX_DIR / "sessions"

OUTPUT_SCHEMA_FILE = WORK_DIR / "output_schema.json"
OUTPUT_LAST_MESSAGE_FILE = WORK_DIR / "output_last_message.json"

USER_AUTH_JSON_FILE = Path.home() / ".codex" / "auth.json"

DB_SQLITE_FILE = WORK_DIR / "db.sqlite"
