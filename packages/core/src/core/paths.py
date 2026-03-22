from pathlib import Path


def get_work_dir(root_dir: Path) -> Path:
    return root_dir / ".work"


def get_agent_dir(root_dir: Path) -> Path:
    return root_dir / "agent"


def get_logs_dir(root_dir: Path) -> Path:
    return get_work_dir(root_dir) / "logs"


def get_codex_dir(root_dir: Path) -> Path:
    return get_work_dir(root_dir) / "codex"


def get_sessions_dir(root_dir: Path) -> Path:
    return get_codex_dir(root_dir) / "sessions"


def get_output_schema_file(root_dir: Path) -> Path:
    return get_work_dir(root_dir) / "output_schema.json"


def get_output_last_message_file(root_dir: Path) -> Path:
    return get_work_dir(root_dir) / "output_last_message.json"


def get_db_sqlite_file(root_dir: Path) -> Path:
    return get_work_dir(root_dir) / "db.sqlite"


def get_communication_mod_dir(root_dir: Path) -> Path:
    return root_dir / "third_party" / "CommunicationMod"


def get_build_mod_work_dir(root_dir: Path) -> Path:
    return get_work_dir(root_dir) / "build_mod"


def get_build_mod_staged_mod_jar(root_dir: Path) -> Path:
    return get_build_mod_work_dir(root_dir) / "mods" / "CommunicationMod.jar"


def get_build_mod_default_java_home(home_dir: Path) -> Path:
    return home_dir / ".sdkman" / "candidates" / "java" / "8.0.482-zulu"


def get_build_mod_default_steam_apps_dir(home_dir: Path) -> Path:
    return home_dir / "Library" / "Application Support" / "Steam" / "steamapps"


def get_build_mod_default_slay_the_spire_dir(home_dir: Path) -> Path:
    return get_build_mod_default_steam_apps_dir(home_dir) / "common" / "SlayTheSpire"


def get_build_mod_slay_the_spire_resources_dir(slay_the_spire_dir: Path) -> Path:
    return slay_the_spire_dir / "SlayTheSpire.app" / "Contents" / "Resources"


def get_build_mod_slay_the_spire_jar(slay_the_spire_dir: Path) -> Path:
    return (
        get_build_mod_slay_the_spire_resources_dir(slay_the_spire_dir)
        / "desktop-1.0.jar"
    )


def get_build_mod_default_slay_the_spire_jar(home_dir: Path) -> Path:
    return get_build_mod_slay_the_spire_jar(
        get_build_mod_default_slay_the_spire_dir(home_dir)
    )


def get_build_mod_default_steam_workshop_dir(home_dir: Path) -> Path:
    return (
        get_build_mod_default_steam_apps_dir(home_dir)
        / "workshop"
        / "content"
        / "646570"
    )


def get_build_mod_modthespire_jar(steam_workshop_dir: Path) -> Path:
    return steam_workshop_dir / "1605060445" / "ModTheSpire.jar"


def get_build_mod_default_modthespire_jar(home_dir: Path) -> Path:
    return get_build_mod_modthespire_jar(
        get_build_mod_default_steam_workshop_dir(home_dir)
    )


def get_build_mod_basemod_jar(steam_workshop_dir: Path) -> Path:
    return steam_workshop_dir / "1605833019" / "BaseMod.jar"


def get_build_mod_default_basemod_jar(home_dir: Path) -> Path:
    return get_build_mod_basemod_jar(get_build_mod_default_steam_workshop_dir(home_dir))


def get_build_mod_installed_mod_jar(mods_dir: Path) -> Path:
    return mods_dir / "CommunicationMod.jar"


def get_build_mod_default_installed_mod_jar(home_dir: Path) -> Path:
    return get_build_mod_installed_mod_jar(
        get_build_mod_slay_the_spire_resources_dir(
            get_build_mod_default_slay_the_spire_dir(home_dir)
        )
        / "mods"
    )


ROOT_DIR = Path(__file__).resolve().parents[4]
HOME_DIR = Path.home()

WORK_DIR = get_work_dir(ROOT_DIR)
AGENT_DIR = get_agent_dir(ROOT_DIR)
COMMUNICATION_MOD_DIR = get_communication_mod_dir(ROOT_DIR)

LOGS_DIR = get_logs_dir(ROOT_DIR)
BRIDGE_LOG_FILE = LOGS_DIR / "bridge.log"
STS_LOG_FILE = LOGS_DIR / "sts.log"

CODEX_DIR = get_codex_dir(ROOT_DIR)
SESSIONS_DIR = get_sessions_dir(ROOT_DIR)

OUTPUT_SCHEMA_FILE = get_output_schema_file(ROOT_DIR)
OUTPUT_LAST_MESSAGE_FILE = get_output_last_message_file(ROOT_DIR)

BUILD_MOD_WORK_DIR = get_build_mod_work_dir(ROOT_DIR)
BUILD_MOD_STAGED_MOD_JAR = get_build_mod_staged_mod_jar(ROOT_DIR)

BUILD_MOD_DEFAULT_JAVA_HOME = get_build_mod_default_java_home(HOME_DIR)
BUILD_MOD_DEFAULT_SLAY_THE_SPIRE_JAR = get_build_mod_default_slay_the_spire_jar(
    HOME_DIR
)
BUILD_MOD_DEFAULT_MODTHESPIRE_JAR = get_build_mod_default_modthespire_jar(HOME_DIR)
BUILD_MOD_DEFAULT_BASEMOD_JAR = get_build_mod_default_basemod_jar(HOME_DIR)
BUILD_MOD_DEFAULT_INSTALLED_MOD_JAR = get_build_mod_default_installed_mod_jar(HOME_DIR)

USER_AUTH_JSON_FILE = HOME_DIR / ".codex" / "auth.json"

DB_SQLITE_FILE = get_db_sqlite_file(ROOT_DIR)
