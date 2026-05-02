# AI Plays Slay the Spire

> 이 문서는 AI가 Harry의 지시에 따라 작성합니다.

**Harry**와 AI 코딩 에이전트가 함께 만드는 Slay the Spire 자동 플레이 봇입니다.
목표는 승천 0 심장 클리어. 하지만 과정에서 배우는 것이 더 중요합니다.

## 무엇이 특별한가

대부분의 게임 봇은 "이 판을 이기는 것"만 목표로 합니다. 이 프로젝트는 **Hindsight 장기기억**으로 각 런의 전략적 교훈을 축적하고, 다음 런에서 회상해 활용합니다. 외부 메모리 뱅크에 기억을 쌓고 검색하는 구조입니다.

단순한 게임 에이전트가 아니라, **"경험으로부터 학습하는 LLM 에이전트"**를 만드는 실험입니다.

## 협업 방식

Harry는 코드를 직접 쓰지 않습니다. AI 에이전트(Pi)와 협업합니다.

| Harry | AI 에이전트 |
|-------|------------|
| 방향 설정, 전략적 제안 | 코드 작성, 리팩토링 |
| 피드백, 질문, 검증 | 로그 분석, 데이터 조사 |
| 크리티컬한 제어 결정 | 세션 실행, 모니터링 |

### 협업에서 배운 것

- **AI는 통찰력을 발휘해야 합니다.** 시키는 대로만 하지 말고, 데이터에서 스스로 패턴을 발견해야 합니다.
- **문서화는 사고 구조를 바꿉니다.** AGENTS.md에 상태, 발견, 가설을 기록하면서 체계적으로 접근하게 되었습니다.
- **Hindsight 관찰은 durable pattern입니다.** 순간적인 HP/에너지 변화를 쌓으면 노이즈만 생깁니다. 의미 있는 기억은 "어떤 선택을 했고, 왜 그랬고, 다음에 어떻게 할 것인가"입니다.

## 현재 상태

### 인프라
- LLM: crof.ai (reasoning_effort="high")
- 장기기억: Hindsight `sts-v2` 뱅크 (371개 memory units, Python SDK)
- 로깅: JSONL (ai.jsonl, game.jsonl, reasoning.jsonl) + llm_dump

### 발견하고 해결한 문제들
- **recall 쿼리 formulation** — keyword-style 쿼리는 enemy-specific memory를 잘 못 건짐. RecallAgent가 자연어 쿼리를 생성하면서 개선.
- **retain 품질** — 93%가 전투 play-by-play. RetainAgent가 이벤트, 상점, 캠프파이어 등 모든 주요 결정을 커버.
- **state 필터링** — `NOISE_KEYS`가 deck, relics, potions, map을 state에서 제거. 완전히 폐기하여 모든 정보를 state에 포함.
- **MAX_OUTPUT truncation** — `game_cli()`의 20K 제한이 recall JSON을 깨뜨림. 제거하고 recall 자체의 `max_tokens=2048`로 응답 크기 제한.
- **시스템 프롬프트 분리** — 단일 시스템 프롬프트를 에이전트별로 분리. messages는 순수 대화 히스토리만 보관.
- **타입 안전성** — `cast`, `Any`, `type: ignore` 최소화. `isinstance`로 타입 좁히기, `ParsedResponse` 도입.

## 아키텍처

### 3-Agent 루프

```
┌─────────────────────────────────────────────────────┐
│  while True:                                         │
│    trim_messages(messages)                           │
│                                                       │
│  ① recall_analysis = RecallAgent(messages, state)   │
│                                                       │
│  ② PlayAgent(system + messages + state/analysis)    │
│     → tool_calls                                     │
│     messages += assistant_msg                        │
│                                                       │
│  ③ for each tool_call:                               │
│       result = execute_tool(...)                     │
│       messages += tool_result                        │
│       if send_command: state = result                │
│                                                       │
│  ④ trigger = detect_trigger(prev_state, new_state)  │
│     if trigger:                                       │
│       content = RetainAgent(messages, trigger)       │
│       game_cli("retain", content)                    │
└─────────────────────────────────────────────────────┘
```

### 에이전트별 구성

| | RecallAgent | PlayAgent | RetainAgent |
|---|---|---|---|
| **시스템 프롬프트** | `RECALL_AGENT_PROMPT` | `PLAY_AGENT_PROMPT` | `RETAIN_AGENT_PROMPT` |
| **히스토리** | messages (공유) | messages (공유) | messages (공유) |
| **사용자 메시지** | 게임 state JSON | 게임 state + recall 분석 | 트리거 설명 (turn_end, combat_end 등) |
| **도구** | `recall` | `send_command` | 없음 (text 응답) |
| **출력** | 분석 텍스트 | tool_calls | retain content 문자열 |

### 메시지 히스토리 (슬라이딩 윈도우)

`messages`는 시스템 프롬프트 없이 user/assistant/tool 메시지만 보관한다.
`MAX_MESSAGES_CHARS=500K` 초과 시 오래된 턴부터 드롭.

```
messages = [
  {role: "assistant", content: ..., tool_calls: [...]},
  {role: "tool", tool_call_id: ..., content: ...},
  {role: "user", content: "You must use a tool."},
  ...
]
```

각 에이전트 호출 시 시스템 프롬프트를 앞에 붙여서 `call_llm()`에 전달한다.

### 핵심 파일

| 파일 | 역할 |
|------|------|
| `packages/ai/src/ai/main.py` | 메인 루프, trigger detection, recall/retain/play 조율 |
| `packages/ai/src/ai/llm.py` | `call_llm()` retry + client lifecycle, `parse_llm_response()`, `build_assistant_message()` |
| `packages/ai/src/ai/recall_agent.py` | `run_recall_agent()`, RecallAgent 프롬프트, recall 툴 |
| `packages/ai/src/ai/retain_agent.py` | `run_retain_agent()`, RetainAgent 프롬프트, 트리거별 메시지 |
| `packages/ai/src/ai/constants.py` | 시스템 프롬프트, TOOLS, 설정 상수 |
| `packages/game/src/game/cli.py` | 게임 CLI, Hindsight SDK 호출 |
| `packages/proxy/src/proxy/main.py` | HTTP 서버 + WebSocket 클라이언트 |
| `packages/bridge/src/bridge/main.py` | WebSocket 서버 + stdin/stdout 브리지 |

### 데이터 흐름

```
AI → subprocess game CLI → httpx proxy(8766) → websocket bridge(8765)
       → stdin → CommunicationMod → Slay the Spire
```

## 실행

```sh
uv sync --all-packages --locked
git submodule update --init --recursive
export CROF_API_KEY=...
uv run proxy   # 프록시 서버
uv run ai      # AI 에이전트
```

## 로드맵

- [x] 기본 AI 루프, Hindsight 통합
- [x] Python SDK 전환, JSONL 로깅
- [x] reasoning.jsonl (recall↔reasoning 분석 인프라)
- [x] State 필터링 완전 폐기 (deck, map, relics, potions 모두 state에 포함)
- [x] MAX_OUTPUT 제거, call_llm() 추출
- [x] RecallAgent 도입 (auto_recall 대체)
- [x] RetainAgent 도입 (수동 retain 대체)
- [x] PlayAgent 경량화 (send_command 단일 툴)
- [x] 시스템 프롬프트 분리, messages 히스토리 순수화
- [x] 루프 평탄화 (_handle_send_command 해체)
- [~] 뱅크 확장 (다양한 클래스/빌드 런)
- [ ] RecallAgent 쿼리 전략 튜닝
- [ ] Tags, entity labels 도입
- [ ] Reflect 기반 전략 조언
- [ ] **심장 클리어**

---

> 이 프로젝트는 "AI가 경험으로부터 학습하는 방법"을 탐구하는 실험입니다. AI 에이전트와의 협업 자체도 배워가고 있습니다.
