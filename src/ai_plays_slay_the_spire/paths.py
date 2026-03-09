from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]

LOG_DIR = PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

CODEX_HOME = PROJECT_DIR / "codex"

AGENT_DIR = PROJECT_DIR / "agent"

AUTH_JSON = Path.home() / ".codex" / "auth.json"
