from pathlib import Path

PROJECT_DIR = Path().resolve()
PROJECT_FILE = PROJECT_DIR / "pyproject.toml"

LOG_DIR = PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
