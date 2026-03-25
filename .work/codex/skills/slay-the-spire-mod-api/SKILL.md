---
name: slay-the-spire-mod-api
description: Slay the Spire CommunicationMod bridge and local FastAPI wrapper usage. Use when Codex needs to inspect the live game state at `http://localhost:8000`, send commands such as `START`, `STATE`, `CHOOSE`, `PLAY`, `END`, `POTION`, `PROCEED`, `RETURN`, `KEY`, `CLICK`, or explain and troubleshoot the local Mod API and event log.
---

# Slay The Spire Mod Api

## Overview

Use this skill to inspect or drive a locally running Slay the Spire session through the FastAPI bridge at `http://localhost:8000`.
Read [references/mod-api-guide-ko.md](references/mod-api-guide-ko.md) when the user wants a Korean guide, concrete `curl` examples, or live-tested behavior notes.

## Workflow

1. Query the current state with `POST /execute` and the command `STATE`, or inspect recent traffic with `GET /events`.
2. Send commands only when `ready_for_command` is `true`.
3. Restrict the next command to the values in `available_commands`.
4. Read `game_state.screen_type`, `game_state.screen_state`, `game_state.choice_list`, `game_state.combat_state`, `game_state.potions`, and `game_state.map` before deciding.
5. Prefer semantic commands such as `CHOOSE`, `PLAY`, `POTION`, `PROCEED`, `RETURN`, and `END`. Use `KEY` or `CLICK` only when no higher-level command is available.

## Command Notes

- Do not prepend `--command-id=...`; the bridge injects it automatically before forwarding the command to CommunicationMod.
- Do not send `ready`; the bridge sends it automatically during startup.
- Treat `GET /events` as an audit log. Each `message` event stores raw JSON text in `data`, so parse it yourself when you need structured fields.
- Treat `PLAY` card indexes as 1-based and combat target indexes as 0-based.
- Prefer `screen_state.options[].choice_index` for `CHOOSE`.
- Expect a timeout error after about 30 seconds if the underlying game never answers.

## References

- Read [references/mod-api-guide-ko.md](references/mod-api-guide-ko.md) for the Korean guide, verified examples, and command-by-command usage notes.
