from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
LOGS_DIR = ROOT_DIR / "logs"


BRIDGE_LOG_FILE = LOGS_DIR / "bridge.log"


AGENT_DIR = ROOT_DIR / "agent"
CODEX_HOME_DIR = AGENT_DIR / ".codex"
SESSIONS_DIR = CODEX_HOME_DIR / "sessions"

OUTPUT_SCHEMA_FILE = AGENT_DIR / "output_schema.json"
OUTPUT_LAST_MESSAGE_FILE = AGENT_DIR / "output_last_message.json"

AGENT_WORK_DIR = AGENT_DIR / "work"


AUTH_JSON_FILE = Path.home() / ".codex" / "auth.json"
