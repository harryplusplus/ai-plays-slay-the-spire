# STS CLI Reference

## Command Surface

Use the CLI from the repository root:

```bash
uv run sts --help
uv run sts command --help
uv run sts events --help
```

The current command set is:

- `uv run sts command COMMAND`
- `uv run sts events [--limit N]`

`events` defaults to `--limit 3`.

## `command`

`uv run sts command` stores one raw command string in `.work/db.sqlite`. The bridge later reads the oldest pending command and writes it to CommunicationMod.

Use one shell argument for the full command text:

```bash
uv run sts command "state"
uv run sts command "start defect 20"
uv run sts command "play 1 0"
uv run sts command "end"
uv run sts command "choose 1"
uv run sts command "proceed"
uv run sts command "return"
uv run sts command "key map 100"
uv run sts command "click left 960 540"
```

Guidelines:

- Quote command strings containing spaces.
- Preserve the exact raw command the game protocol expects.
- CommunicationMod commands are case-insensitive, but the repository examples use lowercase for consistency.
- Prefer `state` when the user wants current game JSON.
- Avoid `wait` unless the user truly needs it for a multi-frame transition.

## `events`

`uv run sts events` prints a JSON array ordered from oldest to newest within the selected window.

Each event object contains:

- `id`
- `kind`
- `data`
- `created_at`
- `updated_at`

`created_at` and `updated_at` are emitted as ISO 8601 strings in the local timezone of the process.

Event kinds:

- `message`: raw JSON or error text received from CommunicationMod
- `command_recorded`: the bridge wrote a queued command to stdout and marked it recorded
- `command_skipped`: the bridge started up and marked stale pending commands as skipped

Typical verification flow:

```bash
uv run sts command "state"
uv run sts events --limit 1
```

If you need more context, increase `--limit`:

```bash
uv run sts events --limit 10
```

## Bridge and DB Behavior

Implementation details that matter in practice:

- `uv run sts` reads and writes `.work/db.sqlite`.
- The `bridge` process creates the database schema on startup.
- `sts command` writes pending commands but does not talk to the game directly.
- On bridge startup, any leftover pending commands are marked `skipped`, and matching `command_skipped` events are created.
- `sts events` returns recent rows from the `events` table; it does not query the game directly.

When a user reports that `sts command` "did nothing", first check whether:

1. The bridge process is running.
2. `uv run sts events --limit N` shows `command_recorded` or `message`.
3. The raw command text itself is valid for the current game state.
