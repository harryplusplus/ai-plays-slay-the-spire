from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
LOGS_DIR = ROOT_DIR / "logs"

BRIDGE_LOG_FILE = LOGS_DIR / "bridge.log"

CODEX_HOME = ROOT_DIR / ".codex"
SESSIONS_DIR = CODEX_HOME / "sessions"

AGENT_DIR = ROOT_DIR / "agent"
OUTPUT_SCHEMA = AGENT_DIR / "output_schema.json"
OUTPUT_LAST_MESSAGE = AGENT_DIR / "output_last_message.json"

AUTH_JSON = Path.home() / ".codex" / "auth.json"
