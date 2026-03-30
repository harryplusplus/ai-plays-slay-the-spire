from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]

WORK_DIR = ROOT_DIR / ".work"

LOGS_DIR = WORK_DIR / "logs"
BRIDGE_LOG_FILE = LOGS_DIR / "bridge.log"
STS_LOG_FILE = LOGS_DIR / "sts.log"

CODEX_DIR = WORK_DIR / "codex"
DB_SQLITE = WORK_DIR / "db.sqlite"
BUILD_JAR = WORK_DIR / "CommunicationMod.jar"

AGENT_DIR = ROOT_DIR / "agent"

COMMUNICATION_MOD_DIR = ROOT_DIR / "external" / "CommunicationMod"

HOME_DIR = Path.home()

JAVA_HOME_DIR = HOME_DIR / ".sdkman" / "candidates" / "java" / "8.0.482-zulu"

STEAMAPPS_DIR = HOME_DIR / "Library" / "Application Support" / "Steam" / "steamapps"

RESOURCES_DIR = (
    STEAMAPPS_DIR
    / "common"
    / "SlayTheSpire"
    / "SlayTheSpire.app"
    / "Contents"
    / "Resources"
)
DESKTOP_JAR = RESOURCES_DIR / "desktop-1.0.jar"
COMMUNICATION_MOD_JAR = RESOURCES_DIR / "mods" / "CommunicationMod.jar"

WORKSHOP_DIR = STEAMAPPS_DIR / "workshop" / "content" / "646570"
MOD_THE_SPIRE_JAR = WORKSHOP_DIR / "1605060445" / "ModTheSpire.jar"
BASE_MOD_JAR = WORKSHOP_DIR / "1605833019" / "BaseMod.jar"

USER_AUTH_JSON = HOME_DIR / ".codex" / "auth.json"
