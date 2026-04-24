# AI Plays Slay the Spire

[CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod)를 통해 Slay the Spire를 플레이하는 AI 에이전트입니다. AI는 Python LLM 루프이며, 계층형 CLI/proxy/bridge 스택을 통해 게임 명령을 호출합니다. 메모리는 Hindsight 뱅크에 저장됩니다.

## 아키텍처

```
┌─────────────┐   subprocess    ┌─────────────┐     HTTP      ┌──────────────┐
│  AI Agent   │ ───────────────→│  Game CLI   │ ─────────────→│    Proxy     │
│ (packages/ai)│  uv run game   │(packages/game)│  port 8766   │(packages/proxy)│
└─────────────┘               └─────────────┘               └──────────────┘
       │                                                           │
       │                                                           │ WebSocket
       │                                                           ↓
       │                                                    ┌──────────────┐
       │                                                    │    Bridge    │
       │                                                    │(packages/bridge)│
       │                                                    │   port 8765   │
       │                                                    └──────────────┘
       │                                                           │
       │                                                           │ stdin/stdout
       │                    (AI tools: send_command, recall, etc)   │
       ↓                                                           ↓
┌─────────────┐                                            ┌──────────────┐
│ Hindsight   │                                            │ CommunicationMod │
│ CLI         │                                            │   (Java mod)   │
└─────────────┘                                            └──────────────┘
                                                                  │
                                                                  ↓
                                                           ┌──────────────┐
                                                           │ Slay the Spire │
                                                           └──────────────┘
```

### 컴포넌트

| 패키지 | 진입점 / 포트 | 역할 |
|--------|--------------|------|
| `ai` | `uv run ai` | LLM 에이전트 루프. OpenAI 호환 API. 게임 상태를 수신하고 툴을 호출하며, 메모리를 자동으로 recall/retain합니다. |
| `game` | `uv run game <cmd>` | Typer CLI. 서브커맨드: `command`, `deck`, `relics`, `potions`, `map`, `recall`, `retain`. proxy와 HTTP로 통신하며, 상태 JSON에서 불필요한 항목(deck/relics/potions/map)을 필터링합니다. recall/retain은 `hindsight` CLI에 위임합니다. |
| `proxy` | `http://127.0.0.1:8766/command` | FastAPI + WebSocket 클라이언트. SQLite 단조 증가 `command_id` 카운터(`~/.sts/proxy.db`). bridge에 자동 재연결합니다. 요청-응답 패턴, 타임아웃 30초. |
| `bridge` | `ws://127.0.0.1:8765/ws` | FastAPI WebSocket 서버. CommunicationMod에 의해 실행됩니다. stdin/stdout(게임 프로토콜)과 WebSocket(proxy)을 연결합니다. stdout에 "ready" 핸드셰이크를 씁니다. |
| `external/CommunicationMod` | — | Java 모드(git submodule). bridge 프로세스를 실행하고, 게임 상태 JSON을 전달하며, 명령을 실행합니다. |

### 데이터 흐름

1. CommunicationMod가 `uv run bridge`를 실행하고 stdout의 `ready\n`을 기다립니다.
2. 게임 상태가 변경되면 CommunicationMod가 bridge의 stdin으로 JSON을 전송합니다.
3. Bridge가 JSON을 모든 WebSocket 클라이언트(proxy)에 브로드캐스트합니다.
4. Proxy가 JSON의 `command_id`를 보류 중인 HTTP 요청과 매칭합니다.
5. AI 에이전트가 `send_command` 호출 → game CLI → proxy HTTP → proxy WebSocket → bridge stdout → CommunicationMod → 게임.
6. 각 `send_command` 이후 AI가 Hindsight에서 자동으로 recall하여 문맥에 메모리를 추가합니다.
7. AI는 시스템 프롬프트에 따라 모든 명령 이후 `retain`을 호출해야 합니다.

## 설치

```sh
uv sync --all-packages --locked
git submodule update --init --recursive
```

### CommunicationMod 빌드 및 설치

```sh
cd external/CommunicationMod
mvn package
# 생성된 jar를 ModTheSpire mods 디렉토리에 복사
```

### CommunicationMod 설정

파일 경로: `~/Library/Preferences/ModTheSpire/CommunicationMod/config.properties` (macOS)

```properties
command=/absolute/path/to/repo/.venv/bin/python -m bridge
runAtGameStart=true
```

> `command` 경로는 절대 경로여야 합니다. `python -m bridge`는 bridge 패키지를 실행합니다.

### 환경변수

| 변수 | 필요한 패키지 | 설명 |
|------|--------------|------|
| `OPENCODE_API_KEY` | `ai` | LLM API 키 |

AI는 `kimi-k2.6` 모델을 `https://opencode.ai/zen/go/v1` 엔드포인트에서 사용하며, `temperature=0`, `reasoning_effort="high"` 설정입니다.

## 실행

Slay the Spire를 ModTheSpire + CommunicationMod가 활성화된 상태로 실행한 뒤:

```sh
# 터미널 1: proxy (bridge에 자동 연결)
uv run proxy

# 터미널 2: AI 에이전트
uv run ai
```

Bridge는 게임이 로드될 때 CommunicationMod에 의해 자동으로 시작됩니다.

## 게임 CLI

```sh
uv run game command "state"          # 명령 전송 후 필터링된 상태 수신
uv run game command "play 1 0"       # 카드 1을 몬스터 0에게 사용
uv run game command "end"            # 턴 종료
uv run game deck                     # 현재 덱 보기
uv run game relics                   # 현재 유물 보기
uv run game potions                  # 현재 물약 보기
uv run game map                      # 현재 지도 보기
uv run game recall "jaw worm act 1"  # Hindsight 메모리 검색
uv run game retain "learned X"       # Hindsight에 관찰 기록
```

상태 필터링: `game_state`에서 `deck`, `relics`, `potions`, `map` 키를 제거하여 노이즈를 줄입니다. 전용 서브커맨드로 필요할 때 따로 조회합니다.

## AI 툴

AI는 7개의 툴을 가지며, 모두 낶게 game CLI를 호출합니다:

| 툴 | 인자 | 매핑 |
|------|------|------|
| `send_command` | `command: str` | `game command <cmd>` |
| `recall` | `query: str` | `game recall <query>` |
| `retain` | `content: str` | `game retain <content>` |
| `deck` | — | `game deck` |
| `relics` | — | `game relics` |
| `potions` | — | `game potions` |
| `map` | — | `game map` |

### 자동 동작

- **자동 recall**: `send_command`마다 `screen_type`, `room_type`, `act`, `floor`, 몬스터 이름으로 쿼리를 생성합니다(키=값 형식). 직전 턴과 쿼리가 같으면 스킵됩니다.
- **retain 강제**: 시스템 프롬프트가 모든 `send_command` 이후 `retain`을 요구합니다.
- **런 종료 감지**: `in_game=false`가 되면 전체 상태를 `~/.sts/logs/runs.log`에 기록하고, AI에게 요약 retain 후 새 게임 시작을 유도합니다.
- **메시지 트리밍**: 총 메시지 문자 수가 400K를 초과하면 오래된 완전 턴을 제거합니다(tool_call/result 쌍은 유지).
- **LLM 재시도**: API 실패 시 10초 후 재시도합니다.

## 로그 및 상태

| 경로 | 목적 |
|------|------|
| `~/.sts/logs/ai.log` | AI 에이전트 결정, 툴 호출, LLM 응답 |
| `~/.sts/logs/proxy.log` | command_id, bridge 재연결, 타임아웃 |
| `~/.sts/logs/bridge.log` | stdin/stdout 프로토콜 메시지 |
| `~/.sts/logs/game.log` | 게임 CLI 호출, Hindsight 호출 |
| `~/.sts/logs/runs.log` | 런 종료 시 전체 상태 |
| `~/.sts/proxy.db` | SQLite command_id 카운터 |

모든 로그는 로테이팅 파일 핸들러(10MB, 5 백업)를 사용합니다.

## 개발

```sh
# 타입 검사
uv run pyright packages/*/src/**/*.py

# 린트
uv run ruff check packages/*/src/**/*.py
```

## 저장소 구조

```text
.
├── external/CommunicationMod/   # Java 모드(git submodule)
├── packages/
│   ├── ai/                      # LLM 에이전트 루프
│   ├── bridge/                  # WebSocket ↔ stdin/stdout 브리지
│   ├── game/                    # Typer CLI(proxy 클라이언트 + Hindsight)
│   ├── proxy/                   # HTTP API + WebSocket 클라이언트 + SQLite
│   └── tools/                   # 개발 헬퍼(git-submodules, mod 관리)
├── pyproject.toml               # uv workspace 루트
└── uv.lock
```
