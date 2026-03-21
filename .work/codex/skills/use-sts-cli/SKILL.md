---
name: use-sts-cli
description: Explain, invoke, and troubleshoot the `uv run sts` CLI in this repository. Use when Codex needs to show exact `sts` command lines, queue Slay the Spire protocol commands with `uv run sts command`, inspect recent bridge events with `uv run sts events`, or explain how the CLI uses `.work/db.sqlite` with the bridge process.
---

# Use STS CLI

## Overview

Use `uv run sts` from the current working directory in this workspace. The agent already starts in the correct directory, so do not change directories before running it. This CLI is a thin wrapper over the shared SQLite queue that the bridge process uses:

- `command` inserts one raw CommunicationMod command string into `pending_commands`
- `events` prints recent bridge events as JSON

Read [references/cli-reference.md](references/cli-reference.md) for exact syntax, example commands, and event meanings.

## Workflow

1. Run from the current working directory for this workspace. Do not change directories before running `uv run sts`.
2. Prefer the exact entrypoint `uv run sts`; do not replace it with `python -m sts` unless the user explicitly wants packaging details.
3. Translate the user's intent into one raw game command string, then pass it as a single shell argument to `sts command`.
4. Quote command strings that contain spaces, for example:

```bash
uv run sts command "state"
uv run sts command "play 1 0"
uv run sts command "choose 2"
```

5. After queueing a command, inspect recent events with `uv run sts events --limit N`.
6. Interpret event kinds before diagnosing game behavior:
   - `command_recorded`: the bridge consumed the queued command
   - `command_skipped`: the bridge restarted and discarded an old pending command
   - `message`: raw JSON or error text returned from CommunicationMod
7. When reading `message` payloads, do not assume `combat_state` exists outside combat. Newer CommunicationMod payloads may instead expose event-specific fields such as `choice_list`, `screen_state.options`, and `keys`.
8. Avoid suggesting `WAIT` unless multi-step state changes make it necessary.

## Troubleshooting

- If `uv run sts` fails to start, confirm the command is being run from the current working directory for this workspace, and that the workspace dependencies are installed.
- If `command` succeeds but nothing happens in game, the bridge may not be running yet. The bridge is the process that creates the schema for `.work/db.sqlite` and forwards queued commands to the mod.
- If the user wants fresh game state, prefer `uv run sts command "state"` and then `uv run sts events --limit 1`.
- After a CommunicationMod update, first verify the latest `message` payload shape before assuming older jq paths still work.
- If you need implementation details, inspect:
  - `packages/sts/src/sts/app.py`
  - `packages/sts/src/sts/__main__.py`
  - `packages/bridge/src/bridge/bridge.py`
  - `packages/core/src/core/paths.py`
