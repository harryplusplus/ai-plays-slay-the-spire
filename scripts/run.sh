#!/usr/bin/env bash
set -euo pipefail

. "/Users/harry/.local/bin/env"

# cd to root dir
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

uv run --package bridge -m bridge
