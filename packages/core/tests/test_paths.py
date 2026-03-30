from pathlib import Path

from core import paths


def test_paths_are_derived_from_root_dir() -> None:
    root_dir = Path(__file__).resolve().parents[3]
    home_dir = Path.home()
    steamapps_dir = home_dir / "Library" / "Application Support" / "Steam" / "steamapps"
    resources_dir = (
        steamapps_dir
        / "common"
        / "SlayTheSpire"
        / "SlayTheSpire.app"
        / "Contents"
        / "Resources"
    )
    workshop_dir = steamapps_dir / "workshop" / "content" / "646570"

    assert root_dir == paths.ROOT_DIR
    assert root_dir / ".work" == paths.WORK_DIR
    assert paths.LOGS_DIR == paths.WORK_DIR / "logs"
    assert paths.BRIDGE_LOG_FILE == paths.LOGS_DIR / "bridge.log"
    assert paths.STS_LOG_FILE == paths.LOGS_DIR / "sts.log"
    assert paths.CODEX_DIR == paths.WORK_DIR / "codex"
    assert paths.DB_SQLITE == paths.WORK_DIR / "db.sqlite"
    assert paths.BUILD_JAR == paths.WORK_DIR / "CommunicationMod.jar"
    assert root_dir / "agent" == paths.AGENT_DIR
    assert root_dir / "external" / "CommunicationMod" == paths.COMMUNICATION_MOD_DIR
    assert home_dir == paths.HOME_DIR
    assert (
        home_dir / ".sdkman" / "candidates" / "java" / "8.0.482-zulu"
    ) == paths.JAVA_HOME_DIR
    assert steamapps_dir == paths.STEAMAPPS_DIR
    assert resources_dir == paths.RESOURCES_DIR
    assert resources_dir / "desktop-1.0.jar" == paths.DESKTOP_JAR
    assert (
        resources_dir / "mods" / "CommunicationMod.jar" == paths.COMMUNICATION_MOD_JAR
    )
    assert workshop_dir == paths.WORKSHOP_DIR
    assert workshop_dir / "1605060445" / "ModTheSpire.jar" == paths.MOD_THE_SPIRE_JAR
    assert workshop_dir / "1605833019" / "BaseMod.jar" == paths.BASE_MOD_JAR
    assert home_dir / ".codex" / "auth.json" == paths.USER_AUTH_JSON
