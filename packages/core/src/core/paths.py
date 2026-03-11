from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]
LOGS_DIR = ROOT_DIR / "logs"
BRIDGE_LOG_FILE = LOGS_DIR / "bridge.log"
