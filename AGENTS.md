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

### 최근 완료
- [x] reasoning.jsonl 로깅 (recall↔reasoning 쌍)
- [x] Document ID 기반 전투 그룹핑
- [x] Python SDK 전환, JSONL 로깅
- [x] **State 필터링 완전 폐기**: `NOISE_KEYS` 제거. deck, map, relics, potions 모두 state에 포함.
- [x] **draw_pile/discard_pile awareness**: 시스템 프롬프트에 안내 추가
- [x] **MAX_OUTPUT 제거**: `game_cli()`의 20K truncation 제거. recall은 `max_tokens=2048`로 크기 제한.
- [x] **call_llm() 추출**: LLM 호출 + retry 로직을 `llm.py`로 분리. 매 요청마다 client 생성/close. `caller` 파라미터로 에이전트 식별.
- [x] **RecallAgent 도입**: `auto_recall()` 제거. 전용 RecallAgent가 state + 히스토리 기반 자연어 쿼리로 recall 호출. multi-turn 가능.
- [x] **RetainAgent 도입**: 화면 전환 감지로 retain 트리거. RetainAgent가 히스토리 기반으로 retain content 생성.
- [x] **PlayAgent 경량화**: TOOLS에서 recall, retain, deck, map, relics, potions 모두 제거. `send_command`만 남음.
- [x] **시스템 프롬프트 분리**: messages는 순수 대화 히스토리만. 각 에이전트가 자신의 시스템 프롬프트를 call_llm 시점에 주입.
- [x] **루프 평탄화**: `_handle_send_command` 해체. recall → play → execute → retain 흐름이 메인 루프에 평평하게 드러남.
- [x] **parse_llm_response()**: 응답 파싱 로직을 `ParsedResponse` 데이터클래스로 통일.
- [x] **타입 안전성**: `cast`, `Any`, `type: ignore` 최소화. `isinstance`로 타입 좁히기.

## 발견한 것들

### recall은 쿼리 formulation에 민감하다
`IRONCLAD room=MonsterRoomElite act=3 monsters=Giant Head` 같은 keyword-style 쿼리는
enemy-specific memory를 잘 못 건진다. 반면 `"What strategy should IRONCLAD use against
Giant Head in Act 3?"` 같은 자연어 쿼리는 Giant Head 관련 메모리를 1순위로 가져온다.
쿼리 variant 간 Jaccard similarity는 0.08~0.51 — 쿼리를 어떻게 쓰느냐에 따라 완전히
다른 결과 집합이 나온다. RecallAgent가 자연어 쿼리를 생성하면서 이 문제가 개선됨.

### retain은 전투 play-by-play에 치우쳐 있었다 (→ RetainAgent로 해결)
28개 retain 중 93%가 전투 설명. 이벤트 선택, 경로 결정, 캠프파이어, 상점, 빌드 결정 이유
같은 전략적 기억이 거의 없었음. 같은 전투에 3~4번 retain해서 중복도 심함.
→ RetainAgent가 화면 전환을 감지해 자동으로 retain 호출. 전투뿐 아니라 이벤트, 상점,
캠프파이어, 카드 선택 등 모든 주요 결정을 커버.

### state 필터링이 모든 정보를 숨기고 있었다 (해결됨)
`cli.py`의 `filter_game_state`가 `NOISE_KEYS`로 deck, relics, potions, map을
모든 state 응답에서 제거 중이었음. AI가 유물/포션/덱/맵을 전혀 인지하지 못함.
→ `NOISE_KEYS`와 `filter_game_state` 완전 제거. 모든 정보가 state에 포함됨.

### MAX_OUTPUT이 recall JSON을 조용히 깨뜨리고 있었다 (해결됨)
`game_cli()`의 `MAX_OUTPUT=20_000`이 53K짜리 recall JSON을 20K로 잘라서
`json.loads`가 실패. 깨진 JSON 텍스트로 24개 결과만 부분 수신 중이었음.
→ `MAX_OUTPUT` 제거. recall은 `max_tokens=2048`로 응답 크기 자체를 제한.

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
  PlayAgent:   [system: PLAY_SYSTEM_PROMPT] + messages + [user: state + recall 분석]
  RetainAgent: [system: RETAIN_AGENT_PROMPT] + messages + [user: trigger 설명]
```

### LLM 재시도
`call_llm()`이 `MAX_ATTEMPTS=5`까지 exponential backoff. 초과 시 30s sleep 후 리셋.
매 요청마다 client를 새로 생성하고 `close()`하여 connection leak 방지.
`caller` 파라미터로 로그에서 에이전트 식별 가능.

## 할 일

### 지금
1. [ ] RecallAgent + RetainAgent 적용 후 런 품질 평가
2. [ ] `hindsight bank consolidate sts-v2`로 observation 재생성

### 다음
3. [ ] 다양한 클래스/빌드로 런 돌려서 뱅크 확장
4. [ ] Tags 도입 (class, topic, enemy)
5. [ ] RecallAgent 쿼리 전략 튜닝 (multi-query merge 등)

### 나중
6. [ ] Reflect로 전략 조언
7. [ ] Mental model 생성
8. [ ] 심장 클리어

## 아키텍처

### 메인 루프
```
while True:
    trim_messages(messages)

    ① recall_analysis = RecallAgent(messages, current_state_json)
    ② PlayAgent(PLAY_SYSTEM_PROMPT + messages + state/analysis) → tool_calls
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
| 시스템 프롬프트 | `RECALL_AGENT_PROMPT` | `PLAY_SYSTEM_PROMPT` | `RETAIN_AGENT_PROMPT` |
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

### 발견한 버그: CLI/DB 스키마 불일치 (해결됨)
- DB 마이그레이션(2026-04-02): `opinion` 제거, `observation` 추가
- CLI 기본값: 여전히 `[world, experience, opinion]`
- 결과: recall 기본 호출 시 observation 타입 메모리 검색 제외
- 해결: `cli.py`에서 `types=["world", "experience", "observation"]` 명시

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
