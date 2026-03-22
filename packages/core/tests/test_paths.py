from pathlib import Path

from core import paths


def test_paths_are_derived_from_root_dir() -> None:
    root_dir = Path(__file__).resolve().parents[3]
    home_dir = Path.home()

    assert root_dir == paths.ROOT_DIR
    assert root_dir / ".work" == paths.WORK_DIR
    assert root_dir / "agent" == paths.AGENT_DIR
    assert root_dir / "third_party" / "CommunicationMod" == paths.COMMUNICATION_MOD_DIR
    assert paths.LOGS_DIR == paths.WORK_DIR / "logs"
    assert paths.BRIDGE_LOG_FILE == paths.LOGS_DIR / "bridge.log"
    assert paths.CODEX_DIR == paths.WORK_DIR / "codex"
    assert paths.SESSIONS_DIR == paths.CODEX_DIR / "sessions"
    assert paths.OUTPUT_SCHEMA_FILE == paths.WORK_DIR / "output_schema.json"
    assert paths.OUTPUT_LAST_MESSAGE_FILE == paths.WORK_DIR / "output_last_message.json"
    assert paths.BUILD_MOD_WORK_DIR == paths.WORK_DIR / "build_mod"
    assert (
        paths.BUILD_MOD_STAGED_MOD_JAR
        == paths.BUILD_MOD_WORK_DIR / "mods" / "CommunicationMod.jar"
    )
    assert (
        home_dir / ".sdkman" / "candidates" / "java" / "8.0.482-zulu"
        == paths.BUILD_MOD_DEFAULT_JAVA_HOME
    )
    assert (
        home_dir
        / "Library"
        / "Application Support"
        / "Steam"
        / "steamapps"
        / "common"
        / "SlayTheSpire"
        / "SlayTheSpire.app"
        / "Contents"
        / "Resources"
        / "desktop-1.0.jar"
        == paths.BUILD_MOD_DEFAULT_SLAY_THE_SPIRE_JAR
    )
    assert (
        home_dir
        / "Library"
        / "Application Support"
        / "Steam"
        / "steamapps"
        / "workshop"
        / "content"
        / "646570"
        / "1605060445"
        / "ModTheSpire.jar"
        == paths.BUILD_MOD_DEFAULT_MODTHESPIRE_JAR
    )
    assert (
        home_dir
        / "Library"
        / "Application Support"
        / "Steam"
        / "steamapps"
        / "workshop"
        / "content"
        / "646570"
        / "1605833019"
        / "BaseMod.jar"
        == paths.BUILD_MOD_DEFAULT_BASEMOD_JAR
    )
    assert (
        home_dir
        / "Library"
        / "Application Support"
        / "Steam"
        / "steamapps"
        / "common"
        / "SlayTheSpire"
        / "SlayTheSpire.app"
        / "Contents"
        / "Resources"
        / "mods"
        / "CommunicationMod.jar"
        == paths.BUILD_MOD_DEFAULT_INSTALLED_MOD_JAR
    )
    assert Path.home() / ".codex" / "auth.json" == paths.USER_AUTH_JSON_FILE
    assert paths.DB_SQLITE_FILE == paths.WORK_DIR / "db.sqlite"
