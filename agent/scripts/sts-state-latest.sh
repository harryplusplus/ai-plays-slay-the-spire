#!/usr/bin/env bash
set -euo pipefail

limit="${1:-20}"

events_json="$(uv run sts events --limit "$limit")"

if ! latest_message_json="$(
    printf '%s\n' "$events_json" | jq -er '
        map(select(.kind == "message" and (.data | startswith("{"))))
        | last
        | .data
        | fromjson
    '
)"; then
    printf 'No JSON message event found in the last %s events.\n' "$limit" >&2
    exit 1
fi

printf '%s\n' "$latest_message_json"
