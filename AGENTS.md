# AI 에이전트 노트 — Slay the Spire

## 개요
LLM(crof.ai)이 CommunicationMod로 Slay the Spire를 자동 플레이.
목표: 승천 0 심장 클리어. Hindsight 장기기억으로 런 간 학습.

## 현재 상태 (2026-05-02)

### 실행 중
- `sts-ai`, `sts-proxy`, `hs-api`, `hs-web` tmux 세션 정상
- Ironclad 런 진행 중

### 뱅크: `sts-v2`
- **371개** memory units (experience 199, observation 163, world 9)
- 전부 Ironclad, 전부 Strength 빌드 관련
- 9,107 links, 202 documents

## 발견한 것들

### recall은 쿼리 formulation에 민감하다
`IRONCLAD room=MonsterRoomElite act=3 monsters=Giant Head` 같은 keyword-style 쿼리는
enemy-specific memory를 잘 못 건진다. 반면 `"What strategy should IRONCLAD use against
Giant Head in Act 3?"` 같은 자연어 쿼리는 Giant Head 관련 메모리를 1순위로 가져온다.
쿼리 variant 간 Jaccard similarity는 0.08~0.51 — 쿼리를 어떻게 쓰느냐에 따라 완전히
다른 결과 집합이 나온다. RecallAgent가 자연어 쿼리를 생성하면서 이 문제가 개선됨.

### reasoning은 recall보다 game state에 의존한다
reasoning 내용 분석 결과, recall 개념이 reasoning에 등장해도 그건 현재 덱에 있는 카드 이름일 뿐.
LLM은 recall 텍스트보다 state JSON을 직접 보고 판단.
→ `reasoning_logger`가 recall_analysis와 reasoning_content를 함께 기록하여 상관관계 추적 중.

### messages 구조
```
messages (순수 히스토리, 시스템 프롬프트 없음):
  {role: "assistant", content: ..., tool_calls: [...]}
  {role: "tool", tool_call_id: ..., content: ...}
  ...

각 call_llm() 호출 시:
  RecallAgent: [system: RECALL_AGENT_PROMPT] + messages + [user: state JSON]
  PlayAgent:   [system: PLAY_AGENT_PROMPT] + messages + [user: state + recall 분석]
  RetainAgent: [system: RETAIN_AGENT_PROMPT] + messages + [user: trigger 설명]
```

### LLM 재시도
`call_llm()`이 `MAX_ATTEMPTS=5`까지 exponential backoff. 초과 시 30s sleep 후 리셋.
매 요청마다 client를 새로 생성하고 `close()`하여 connection leak 방지.
`caller` 파라미터로 로그에서 에이전트 식별 가능.

### Retain 시스템 — 알려진 문제와 대응법

#### `_detect_trigger` 검증되지 않은 브랜치
`packages/ai/src/ai/main.py`의 `_detect_trigger()`는 다음 SCREEN 전환에서
아직 테스트되지 않음: EVENT→MAP, SHOP_ROOM→MAP, CHEST→COMBAT_REWARD.

ai.jsonl에서 `tool_result`의 screen 전환과 `retain_agent` 이벤트 발생 여부를
비교해서 검증 필요. 수정 시 `packages/ai/tests/`에 단위 테스트 추가.

#### GRID 스크린 (2026-05-02 처리 완료)
`_detect_trigger` 로직:
- `new_screen == "GRID"` → suppress (REST→GRID, SHOP_SCREEN→GRID FALSE POSITIVE 방지)
- `prev_screen == "GRID"` → room 분기: RestRoom→campfire, ShopRoom→shop, EventRoom→event
- MonsterRoom GRID → unmatched fall-through, 정상 무시

## 할 일

### 다음
1. [ ] 다양한 클래스/빌드로 런 돌려서 뱅크 확장
2. [ ] Tags 도입 (class, topic, enemy)
3. [ ] RecallAgent 쿼리 전략 튜닝 (multi-query merge 등)

### 나중
4. [ ] Reflect로 전략 조언
5. [ ] Mental model 생성
6. [ ] 심장 클리어

## 아키텍처

### 메인 루프
```
while True:
    trim_messages(messages)

    ① recall_analysis = RecallAgent(messages, current_state_json)
    ② PlayAgent(PLAY_AGENT_PROMPT + messages + state/analysis) → tool_calls
    ③ messages += assistant_msg
    ④ for each tool_call:
         result = execute_tool(...)
         messages += tool_result
         if send_command: current_state = result
    ⑤ trigger = _detect_trigger(command, current_state, new_state)
       if trigger: RetainAgent(messages, trigger) → game_cli("retain", ...)
```

### 에이전트별 구성

| | RecallAgent | PlayAgent | RetainAgent |
|---|---|---|---|
| 시스템 프롬프트 | `RECALL_AGENT_PROMPT` | `PLAY_AGENT_PROMPT` | `RETAIN_AGENT_PROMPT` |
| 도구 | `recall` | `send_command` | 없음 |
| 사용자 메시지 | 게임 state JSON | state + recall 분석 | 트리거 설명 |
| 출력 | 분석 텍스트 | tool_calls | retain content |

### 패키지
| 패키지 | 진입점 | 역할 |
|--------|--------|------|
| `packages/ai` | `uv run ai` | 3-agent 루프. OpenAI 호환 API로 tool-calling |
| `packages/game` | `uv run game <cmd>` | Typer CLI. proxy HTTP(8766)와 통신. Hindsight SDK |
| `packages/proxy` | `uv run proxy` | FastAPI HTTP 서버(8766) + WebSocket 클라이언트 |
| `packages/bridge` | `uv run bridge` | WebSocket 서버(8765). CommunicationMod stdin/stdout 브리지 |
| `packages/tools` | `uv run tools` | 개발 헬퍼 (게임과 무관) |

### 데이터 흐름
```
AI → subprocess game CLI → httpx proxy(8766) → websocket bridge(8765)
       → stdin → CommunicationMod → Slay the Spire
```

### 핵심 파일
- `packages/ai/src/ai/main.py` — 메인 루프, trigger detection, `_build_user_message`
- `packages/ai/src/ai/llm.py` — `call_llm()`, `parse_llm_response()`, `build_assistant_message()`
- `packages/ai/src/ai/recall_agent.py` — `run_recall_agent()`, RecallAgent 프롬프트/툴
- `packages/ai/src/ai/retain_agent.py` — `run_retain_agent()`, RetainAgent 프롬프트/트리거
- `packages/ai/src/ai/constants.py` — 시스템 프롬프트 3종, TOOLS, 설정 상수
- `packages/game/src/game/cli.py` — 게임 CLI, Hindsight SDK 호출
- `packages/proxy/src/proxy/main.py` — HTTP 서버 + WebSocket 클라이언트
- `packages/bridge/src/bridge/main.py` — WebSocket 서버 + stdin/stdout 브리지

## Hindsight

소스코드: `/Users/harry/repo/nailed-it/external/hindsight/`

### recall 파라미터
- `max_tokens=2048` (28개 결과, 24K JSON)
- `types=["world", "experience", "observation"]`
- `budget`은 SDK 기본값(`"mid"`) 사용, 명시적으로 넘기지 않음

## 운영

### 환경변수
| 변수 | 설명 |
|------|------|
| `CROF_API_KEY` | LLM API 키 (crof.ai) |

### tmux 세션
| 세션 | 역할 | 재시작 |
|------|------|--------|
| `sts-ai` | AI 루프 | ai 코드 변경 시 |
| `sts-proxy` | Proxy | proxy 코드 변경 시 |
| `hs-api` | Hindsight API | **절대 건드리지 않음** |
| `hs-web` | Hindsight Web | **절대 건드리지 않음** |

재시작은 반드시 사용자 승인 후. `kill-server` 사용 금지.

### 모니터링
```bash
# 세션 상태
tmux ls

# 최근 이벤트
tail -3 ~/.sts/logs/ai.jsonl | jq -r '"[\(.event)] \(.msg)"'

# 에러 확인 (caller 필드로 에이전트 식별)
jq 'select(.lvl == "ERROR") | {ts, msg, caller}' ~/.sts/logs/ai.jsonl | tail -5

# reasoning.jsonl 증가 체크
wc -l ~/.sts/logs/reasoning.jsonl

# AI 멈춤 감지
jq -r '.ts' ~/.sts/logs/ai.jsonl | tail -1
```

### 로그
| 경로 | 내용 | 포맷 |
|------|------|------|
| `~/.sts/logs/ai.jsonl` | AI 결정, 툴 호출, LLM 응답, agent 이벤트 | JSONL |
| `~/.sts/logs/game.jsonl` | 게임 CLI, Hindsight 호출 | JSONL |
| `~/.sts/logs/reasoning.jsonl` | recall_analysis↔reasoning_content 쌍 | JSONL |
| `~/.sts/logs/llm_dump/` | LLM 호출 직전 messages (시스템 프롬프트 포함) | JSON (최근 10개) |
| `~/.sts/logs/proxy.log` | proxy 연결, 타임아웃 | 텍스트 |
| `~/.sts/logs/bridge.log` | stdin/stdout 프로토콜 | 텍스트 |
| `~/.sts/logs/runs.log` | 런 종료 시 전체 상태 | 텍스트 |

모두 RotatingFileHandler(10MB×5). `jq`로 필터링 가능.

### 알려진 이슈
- **메시지 트리밍**: `MAX_MESSAGES_CHARS=500K` 초과 시 오래된 턴부터 드롭.
- **LLM 재시도**: `call_llm()`이 `MAX_ATTEMPTS=5`까지 exponential backoff. 초과 시 30s sleep 후 리셋.
- **런 종료**: `in_game=false` → runs.log 기록 + RetainAgent("run_end") 호출.
- **START 직후 오탐지**: 새 런 시작 시 `in_game=null`을 run_end로 착각해 불필요한 retain 발생 가능.

## 개발 워크플로우

Python 파일 변경 후 반드시:
```bash
uv run ruff format
uv run ruff check --fix
uv run pyright
```
셋 다 통과해야 커밋.

## AI 에이전트 지침

### Harry의 지시 스타일
- **통찰력을 발휘할 것** — 시키는 대로만 하지 말고, 데이터를 보고 스스로 패턴과 문제를 발견해.
- **분석 먼저, 구현은 나중에** — 코드부터 고치려 들지 말고, 로그/데이터를 충분히 조사한 후 계획을 제시해.
- **간결하고 담백하게** — 같은 정보를 길게 늘어쓰지 마. 핵심만.
- **커밋은 Harry가 리뷰 후** — 작업 완료 후 바로 커밋하지 말고 검토받을 것.

### 문서화 원칙
- **코드가 문서보다 우선** — 불일치 시 코드가 정답. 코드 변경 후 문서 즉시 업데이트.
- **AGENTS.md는 반말, README는 "입니다"체** — AGENTS.md는 Harry와의 대화, README는 외부용.
- **구체적 예시** — 추상적 표현 대신 실제 retain/recall 예시로.
- **살아있는 로드맵** — `[x]` 완료, `[~]` 진행 중, `[ ]` 미완료.
