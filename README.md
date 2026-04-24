# AI Plays Slay the Spire

An AI agent that plays Slay the Spire via [CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod). The agent is a Python LLM loop that calls game commands through a layered CLI/proxy/bridge stack. Memory is stored in a Hindsight bank.

## Architecture

```
┌─────────────┐     HTTP      ┌──────────────┐     WebSocket   ┌──────────────┐
│  AI Agent   │ ─────────────→│    Proxy     │ ──────────────→│    Bridge    │
│ (packages/ai)│   port 8766   │ (packages/proxy)│  port 8765   │(packages/bridge)│
└─────────────┘               └──────────────┘               └──────────────┘
       │                                                           │
       │ tools: send_command, recall, retain, deck, relics,        │ stdin/stdout
       │       potions, map                                         │
       ↓                                                           ↓
┌─────────────┐                                            ┌──────────────┐
│  Game CLI   │ ← Hindsight CLI (recall/retain)           │ CommunicationMod │
│ (packages/  │                                            │   (Java mod)   │
game)         │                                            └──────────────┘
└─────────────┘                                                   │
                                                                  ↓
                                                           ┌──────────────┐
                                                           │ Slay the Spire │
                                                           └──────────────┘
```

### Components

| Package | Port / CLI | Role |
|---------|-----------|------|
| `ai` | `uv run ai` | LLM agent loop. OpenAI-compatible API. Receives game state, calls tools, auto-recalls and retains memory. |
| `game` | `uv run game <cmd>` | Typer CLI. Subcommands: `command`, `deck`, `relics`, `potions`, `map`, `recall`, `retain`. Talks to proxy via HTTP. Filters noise (deck/relics/potions/map) from state JSON. Recall/retain delegate to Hindsight CLI. |
| `proxy` | `http://127.0.0.1:8766/command` | FastAPI + WebSocket client. SQLite monotonic command_id counter (`~/.sts/proxy.db`). Reconnects to bridge automatically. Request-response pattern with 30s timeout. |
| `bridge` | `ws://127.0.0.1:8765/ws` | FastAPI WebSocket server launched by CommunicationMod. Bridges stdin/stdout (game protocol) with WebSocket (proxy). Writes "ready" handshake on stdout. |
| `external/CommunicationMod` | — | Java mod (git submodule). Launches bridge process, forwards game state JSON, executes commands. |

### Data Flow

1. CommunicationMod launches `uv run bridge` and waits for `ready\n` on stdout.
2. Game state changes → CommunicationMod sends JSON to bridge stdin.
3. Bridge broadcasts JSON to all WebSocket clients (proxy).
4. Proxy matches `command_id` in the JSON to pending HTTP requests.
5. AI agent calls `send_command` → game CLI → proxy HTTP → proxy WebSocket → bridge stdout → CommunicationMod → game.
6. After each `send_command`, AI auto-recalls from Hindsight and appends memories to context.
7. AI must `retain` after every command (enforced in system prompt).

## Setup

```sh
uv sync --all-packages --locked
git submodule update --init --recursive
```

### Build & Install CommunicationMod

```sh
cd external/CommunicationMod
mvn package
# Copy the jar to your ModTheSpire mods directory
```

### CommunicationMod Config

File: `~/Library/Preferences/ModTheSpire/CommunicationMod/config.properties` (macOS)

```properties
command=/absolute/path/to/repo/.venv/bin/python -m bridge
runAtGameStart=true
```

> The `command` path must be absolute. `python -m bridge` launches the bridge package.

### Environment Variables

| Variable | Required By | Description |
|----------|-------------|-------------|
| `OLLAMA_API_KEY` | `ai` | API key for the LLM endpoint |
| `HINDSIGHT_*` | `game` | Hindsight server config (URL, API key, etc.) |

The AI uses `glm-5.1` via `https://ollama.com/v1` with `temperature=0` and `reasoning_effort="high"`.

## Running

Start Slay the Spire with ModTheSpire + CommunicationMod enabled. Then:

```sh
# Terminal 1: proxy (auto-connects to bridge)
uv run proxy

# Terminal 2: AI agent
uv run ai
```

The bridge is started automatically by CommunicationMod when the game loads.

## Game CLI

```sh
uv run game command "state"          # Send raw command, get filtered state
uv run game command "play 1 0"       # Play card 1 targeting monster 0
uv run game command "end"            # End turn
uv run game deck                     # Show deck (extracted from state)
uv run game relics                   # Show relics
uv run game potions                  # Show potions
uv run game map                      # Show map
uv run game recall "jaw worm act 1"  # Search Hindsight memory
uv run game retain "learned X"       # Store observation in Hindsight
```

State filtering: `deck`, `relics`, `potions`, `map` keys are stripped from `game_state` to reduce noise. Use the dedicated subcommands to view them on demand.

## AI Tools

The AI has 7 tools, all calling the game CLI internally:

| Tool | Args | Maps to |
|------|------|---------|
| `send_command` | `command: str` | `game command <cmd>` |
| `recall` | `query: str` | `game recall <query>` |
| `retain` | `content: str` | `game retain <content>` |
| `deck` | — | `game deck` |
| `relics` | — | `game relics` |
| `potions` | — | `game potions` |
| `map` | — | `game map` |

### Auto Behaviors

- **Auto recall**: After every `send_command`, builds a query from `screen_type`, `room_type`, `act`, `floor`, and monster names (key=value format). Skipped if the query hasn't changed since last turn.
- **Retain enforcement**: System prompt requires `retain` after every `send_command`.
- **Run-end detection**: When `in_game=false`, the full state is logged to `~/.sts/logs/runs.log` and the AI is prompted to retain a summary and start a new game.
- **Message trimming**: When total message chars exceed 400K, oldest complete turns are dropped (preserving tool_call/result pairs).
- **LLM retry**: API failures retry after 10s.

## Logs & State

| Path | Purpose |
|------|---------|
| `~/.sts/logs/ai.log` | AI agent decisions, tool calls, LLM responses |
| `~/.sts/logs/proxy.log` | Command IDs, bridge reconnects, timeouts |
| `~/.sts/logs/bridge.log` | Stdin/stdout protocol messages |
| `~/.sts/logs/game.log` | Game CLI invocations, Hindsight calls |
| `~/.sts/logs/runs.log` | Full run-end states |
| `~/.sts/proxy.db` | SQLite command_id counter |

All logs use rotating file handlers (10MB, 5 backups).

## Development

```sh
# Type check
uv run pyright packages/*/src/**/*.py

# Lint
uv run ruff check packages/*/src/**/*.py
```

## Repository Layout

```text
.
├── external/CommunicationMod/   # Java mod (git submodule)
├── packages/
│   ├── ai/                      # LLM agent loop
│   ├── bridge/                  # WebSocket ↔ stdin/stdout bridge
│   ├── game/                    # Typer CLI (proxy client + Hindsight)
│   └── proxy/                   # HTTP API + WebSocket client + SQLite
├── pyproject.toml               # uv workspace root
└── uv.lock
```