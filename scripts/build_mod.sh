#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
steamapps_dir="${STEAM_APPS_DIR:-$HOME/Library/Application Support/Steam/steamapps}"
slay_the_spire_dir="${SLAY_THE_SPIRE_DIR:-$steamapps_dir/common/SlayTheSpire}"
workshop_dir="${STEAM_WORKSHOP_DIR:-$steamapps_dir/workshop/content/646570}"
maven_repo_dir="$repo_root/.work/m2"
sts_mods_dir="${STS_MODS_DIR:-$slay_the_spire_dir/SlayTheSpire.app/Contents/Resources/mods}"

find_jar() {
  local search_root="$1"
  local jar_name="$2"

  find "$search_root" -type f -name "$jar_name" -print -quit 2>/dev/null
}

require_file() {
  local path="$1"
  local label="$2"

  if [[ ! -f "$path" ]]; then
    printf 'Missing %s: %s\n' "$label" "$path" >&2
    exit 1
  fi
}

link_jar() {
  local source_path="$1"
  local dest_path="$2"

  ln -sfn "$source_path" "$dest_path"
}

cd "$repo_root"
set +u
source "$HOME/.sdkman/bin/sdkman-init.sh"
sdk use java 8.0.482-zulu
set -u

desktop_jar="$(find_jar "$slay_the_spire_dir" "desktop-1.0.jar")"
modthespire_jar="$(find_jar "$workshop_dir" "ModTheSpire.jar")"
basemod_jar="$(find_jar "$workshop_dir" "BaseMod.jar")"

require_file "$desktop_jar" "Slay the Spire desktop JAR"
require_file "$modthespire_jar" "ModTheSpire JAR"
require_file "$basemod_jar" "BaseMod JAR"

mkdir -p agent/lib agent/_ModTheSpire/mods
mkdir -p "$maven_repo_dir"
mkdir -p "$sts_mods_dir"

link_jar "$desktop_jar" "agent/lib/desktop-1.0.jar"
link_jar "$modthespire_jar" "agent/lib/ModTheSpire.jar"
link_jar "$basemod_jar" "agent/lib/BaseMod.jar"

cd agent/CommunicationMod
mvn -Dmaven.repo.local="$maven_repo_dir" clean package

cd "$repo_root"
link_jar "$repo_root/agent/_ModTheSpire/mods/CommunicationMod.jar" "$sts_mods_dir/CommunicationMod.jar"
