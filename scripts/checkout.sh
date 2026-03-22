#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$repo_root"
git submodule sync --recursive
git submodule update --init --recursive

printf 'Checkout is ready.\n'
printf 'Submodules are initialized. You can now run ./scripts/build_mod.sh.\n'
