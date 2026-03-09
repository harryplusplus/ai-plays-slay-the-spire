#!/usr/bin/env bash
set -euo pipefail

. "/Users/harry/.local/bin/env"

# cd to project dir
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

uv run -m app
