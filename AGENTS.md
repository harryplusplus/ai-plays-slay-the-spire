# AI 에이전트 노트 — Slay the Spire

## 프로젝트 개요
LLM(kimi-k2.6 via OpenCode)이 Slay the Spire를 CommunicationMod를 통해 플레이하는 자동화 봇.

## 패키지 구조 (실제)

| 패키지 | 진입점 | 역할 |
|--------|--------|------|
| `packages/ai` | `uv run ai` | LLM 에이전트 루프. OpenAI 호환 API. `subprocess`로 `game` CLI를 호출함. |
| `packages/game` | `uv run game <cmd>` | Typer CLI. 서브커맨드: `command`, `deck`, `relics`, `potions`, `map`, `recall`, `retain`. proxy HTTP(8766)와 통신. `recall`/`retain`은 `hindsight` CLI를 직접 호출. |
| `packages/proxy` | `uv run proxy` | FastAPI HTTP 서버(8766) + WebSocket 클라이언트. bridge(8765)에 자동 재연결. SQLite로 `command_id` 카운터 관리(`~/.sts/proxy.db`). |
| `packages/bridge` | `uv run bridge` | FastAPI WebSocket 서버(8765). CommunicationMod의 stdin/stdout과 WebSocket을 연결. stdout에 `ready\n`을 쓰고 시작 대기. |
| `packages/tools` | `uv run tools` | 개발 헬퍼. `git-submodules`, `mod` 관리용. 게임 플레이와 직접 무관. |

## 데이터 흐름

```
AI (packages/ai)
  → subprocess(["uv", "run", "game", ...])
    → Game CLI (packages/game)
      → httpx.post("http://127.0.0.1:8766/command")
        → Proxy (packages/proxy)
          → websockets.send() → Bridge (packages/bridge)
            → sys.stdout.write() → CommunicationMod (Java mod)
              → Slay the Spire
```

반대 방향(게임 상태)도 동일 경로로 전달됨.

## 핵심 파일

- `packages/ai/src/ai/main.py` — 메인 AI 루프, 툴 정의, 시스템 프롬프트
- `packages/game/src/game/cli.py` — 게임 CLI (proxy 클라이언트 + Hindsight 호출)
- `packages/proxy/src/proxy/main.py` — HTTP 서버 + WebSocket 클라이언트 + SQLite
- `packages/bridge/src/bridge/main.py` — WebSocket 서버 + stdin/stdout 브리지

## 환경변수

| 변수 | 필요한 패키지 | 설명 |
|------|--------------|------|
| `OPENCODE_API_KEY` | `ai` | LLM API 키 (OpenCode) |

## Retain(기억 저장) 전략

- 시스템 프롬프트: **"모든 `send_command` 이후 반드시 `retain`을 호출해야 함"**
- `send_command` 직후 주입되는 유저 메시지에 명시적으로 retain 강제:
  > "지금 당장 retain을 호출해야 한다. 무슨 일이 일어났고, 무엇을 배웠는지 기록하라. 예외는 없다."
- 자동 recall: `screen_type`, `room_type`, `act`, `floor`, 몬스터 이름 기반 쿼리 생성. 직전 턴과 쿼리가 같으면 스킵.

## 알려진 이슈 / 주의사항

- **Retain 빈도**: AI가 실제로 매 커맨드 후 retain을 호출하는지 지속 모니터링 필요. 여전히 걸러지면 상태 머신 도입 검토.
- **메시지 트리밍**: 총 메시지 문자 수가 400K 초과 시 오래된 완전 턴(assistant+tool+user)을 드롭. 시스템 메시지는 보존.
- **LLM 재시도**: API 실패 시 10초 후 재시도.
- **런 종료**: `in_game=false` 감지 시 `~/.sts/logs/runs.log`에 전체 상태 기록 + "retain 후 새 게임 시작" 유도.
- **프록시 타임아웃**: 30초. 브리지 재연결은 자동.

## 로그 위치

| 경로 | 목적 |
|------|------|
| `~/.sts/logs/ai.log` | AI 결정, 툴 호출, LLM 응답 |
| `~/.sts/logs/game.log` | 게임 CLI 호출, Hindsight 호출 |
| `~/.sts/logs/proxy.log` | command_id, 브리지 재연결, 타임아웃 |
| `~/.sts/logs/bridge.log` | stdin/stdout 프로토콜 메시지 |
| `~/.sts/logs/runs.log` | 런 종료 시 전체 상태 |
| `~/.sts/proxy.db` | SQLite command_id 카운터 |

모든 로그는 RotatingFileHandler(10MB, 5 백업) 사용.
