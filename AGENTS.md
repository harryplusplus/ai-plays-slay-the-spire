# AI 에이전트 노트 — Slay the Spire

> **아키텍처, 에이전트 구성, 데이터 흐름, 핵심 파일, Recall/Retain 파라미터 등은 README.md를 참고.**
> 이 파일은 프로젝트 내부자를 위한 운영 노트, 발견한 것들, 할 일만 다룬다.

## 개요
LLM이 CommunicationMod로 Slay the Spire를 자동 플레이.
목표: 승천 0 심장 클리어. Hindsight 장기기억으로 런 간 학습.

## 현재 상태 (2026-05-05)

- `sts-ai`, `sts-proxy`, `hs-api`, `hs-web` tmux 세션 정상
- **Defect 전용 플레이로 전환** — 시스템 프롬프트에서 DEFECT만 사용하도록 강제
- 뱅크 `sts-v2`: **921** memory units (experience 463, observation 437, world 21), 25,462 links, 281 documents
- 현재까지는 전부 Ironclad/Strength 빌드 (Defect 런 시작 시점)

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
→ `reasoning_logger`가 recall_results와 reasoning_content를 함께 기록하여 상관관계 추적 중.

### retain 품질은 단기기억 깊이에 비례한다
RetainAgent는 현재 messages(단기기억)를 컨텍스트로 받아 전략적 고찰을 생성한다.
messages가 충분히 길어야 — 즉 최근 여러 게임 턴의 선택과 결과를 모두 볼 수 있어야 —
단순한 플레이-by-플레이 관찰이 아닌 `"왜 그 선택이 좋았는가"` 수준의 통찰이 나온다.
단기기억이 짧으면 retain 결과물이 근시안적이다: "HP 5 손실" 같은 표면 관찰에 머무르고
"손실을 감수한 대신 Strength 3을 얻었다" 같은 트레이드오프 분석이 안 나온다.
따라서 summarize_turns를 늘린 것은 play뿐 아니라 retain 품질 향상에도 기여한다.

### Retain 시스템 — 알려진 문제와 대응법

#### `_detect_trigger` 검증되지 않은 브랜치
`packages/ai/src/ai/main.py`의 `_detect_trigger()`는 다음 SCREEN 전환에서
아직 테스트되지 않음: EVENT→MAP, CHEST→COMBAT_REWARD.
(`SHOP_ROOM→MAP`은 `SHOP_ROOM`이 room_type이라 screen_type 기준인 prev_screen으로 도달 불가 → dead code.)

ai.jsonl에서 `tool_result`의 screen 전환과 `retain_agent` 이벤트 발생 여부를
비교해서 검증 필요. 수정 시 `packages/ai/tests/`에 단위 테스트 추가.

#### COMBAT_END 트리거
전투 종료 감지는 `NONE`/`HAND_SELECT` → `COMBAT_REWARD` screen 전환으로 처리:
- 직전 screen이 `NONE`(첫 전투) 또는 `HAND_SELECT`(멀티페이즈 전투 끝)이고
  새 screen이 `COMBAT_REWARD`이면 `combat_end` 트리거 발생.
- 다른 전투 관련 screen 전환(예: COMBAT_REWARD→MAP)은 retain 대상이 아님.

#### GRID 스크린 (2026-05-02 처리 완료)
`_detect_trigger` 로직:
- `new_screen == "GRID"` → suppress (REST→GRID, SHOP_SCREEN→GRID FALSE POSITIVE 방지)
- `prev_screen == "GRID"` → room 분기: RestRoom→campfire, ShopRoom→shop, EventRoom→event
- MonsterRoom GRID → unmatched fall-through, 정상 무시

## 할 일

### 다음
1. [~] Defect 전용 플레이 — 시스템 프롬프트에서 DEFECT 강제, Defect 빌드 메모리 축적 시작
2. [ ] Tags 도입 (class, topic, enemy)
3. [ ] RecallAgent 쿼리 전략 튜닝 (multi-query merge 등)

### 완료
- [x] **메시지 트리밍 개선** — char 기반(MAX_MESSAGES_CHARS=500K)에서 turn 기반으로 변경. 최근 3턴 full + 이전 32턴 summarized(assistant content 보존, tool content placeholder) 구조. 상태 JSON 축적으로 인한 컨텍스트 오염 제거.
- [x] **트리밍 범위 확장** — 20→32 summarized turns, 2→3 full keep으로 증가. StS는 덱 순환이 핵심인데, 한 게임 턴이 평균 7행위(14메시지)라 20턴으로는 ~3게임턴밖에 기억 못 함. 32턴으로 ~5게임턴 기억 가능해 웬만한 덱 순환 커버. 200K 컨텍스트 기준 60K근처이므로 문제 없음.
- [x] **루프 평탄화** — `_handle_send_command` 해체, 단일 루프 구조로 단순화.
- [x] **스크린샷 비전 지원** — Recall/Play/Retain 세 에이전트 모두 현재 화면 이미지를 ephemeral하게 수신. messages에 축적 안 됨.

### 나중
4. [ ] Reflect로 전략 조언
5. [ ] Mental model 생성
6. [ ] 심장 클리어

## Hindsight

소스코드: `/Users/harry/repo/nailed-it/external/hindsight/`

- 뱅크 `sts-v2`: **921** memory units (experience 463, observation 437, world 21), 25,462 links, 281 documents
- 현재까지는 전부 Ironclad/Strength 빌드. Defect 런 쌓이면 업데이트.

## 알려진 이슈

- **메시지 트리밍**: `trim_messages()`가 루프 시작 시 assistant 메시지 기준 최근 3개(fully preserved) + 이전 32개(assistant content 보존, tool content placeholder)까지 유지. 그 이전은 전부 삭제. byte 기반 트리밍은 폐기됨.
  200K 컨텍스트 중 text tokens는 ~60K (play 기준). 32+3으로 늘려도 ~63K, 여유 있음.
  StS 특성상 행위 1번이 메시지 2개를 차지. 한 게임 턴은 평균 7행위(패에 따라 10+). 35개 메시지(assistant 기준) 이상을 확보해야 덱 순환을 따라잡을 수 있음.
- **LLM 재시도**: `call_llm()`이 에러 타입별로 재시도. 500/4xx: `MAX_ATTEMPTS=5`까지 exponential backoff, 초과 시 30s sleep 후 리셋. 429: attempt 리셋 없이 backoff(최대 120s). connection/기타 에러: RETRY_DELAY(10s) 고정 재시도.
- **런 종료**: `in_game=false` → run.jsonl 기록 + RetainAgent("run_end") 호출.
- **START 직후 오탐지**: (해결됨) `_detect_trigger()`가 `in_game is False` strict 비교를 사용하므로 `null`/`None`은 run_end로 감지되지 않음.
- **`tool_choice` 미지원**: OpenAI compat API는 `tool_choice` 파라미터를 지원하지 않음. 따라서 모델이 무조건 tool call을 하도록 강제하거나, 특정 tool(`recall`)만 선택하게 강제할 수 없음. 이 제약으로 인해 recall agent가 tool call을 생략하고 텍스트로 응답하거나(no_tool_calls), 제공된 tools 목록에 없는 `send_command`를 hallucination하는 문제가 발생. 해결은 구조적 접근(prompt/history 정제)에 의존해야 함.
- **History contamination (recall agent)**: `run_recall_agent()`가 shared play history(`*messages`)를 그대로 LLM context에 주입. 이 history는 `assistant → send_command → tool result` 패턴이 지배적이라 recall agent의 행동을 bias함. 2026-05-05 기준 recall 호출의 47.2%가 tool call 생략(no_tool_calls), 4.4%가 send_command hallucination. 해결 방안은 AGENTS.md "할 일" 참고.

## 운영

### 환경변수
| 변수 | 설명 |
|------|------|
| `OLLAMA_API_KEY` | LLM API 키 (Ollama OpenAI 호환 엔드포인트, model: kimi-k2.6) |

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
| `~/.sts/logs/llm.jsonl` | LLM 요청/응답 전문 (DEBUG) | JSONL (10MB×5) |
| `~/.sts/logs/proxy.log` | proxy 연결, 타임아웃 | 텍스트 |
| `~/.sts/logs/bridge.log` | stdin/stdout 프로토콜 | 텍스트 |
| `~/.sts/logs/run.jsonl` | 런 종료 시 전체 상태 | JSONL |

모두 RotatingFileHandler(10MB×5). `jq`로 필터링 가능.

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