# AI 에이전트 노트 — Slay the Spire

## 개요
deepseek-v4-pro-precision(crof.ai)이 CommunicationMod로 Slay the Spire를 자동 플레이.
목표: 승천 0 심장 클리어. Hindsight 장기기억으로 런 간 학습.

## 현재 상태 (2026-05-02)

### 실행 중
- `sts-ai`, `sts-proxy`, `hs-api`, `hs-web` tmux 세션 정상
- 두 번째 Ironclad 런 진행 중 (Neow 1HP 축복)

### 뱅크: `sts-v2`
- **78개** memory units (experience 40, observation 36, world 2)
- 전부 Ironclad, 전부 Strength 빌드 관련
- observation이 experience와 거의 동일 — durable pattern 미형성

### 최근 완료
- [x] reasoning.jsonl 로깅 (recall↔reasoning 쌍)
- [x] LLM: deepseek-v4-pro-precision, reasoning_effort="max"
- [x] `last_auto_query` 버그 수정
- [x] Document ID 기반 전투 그룹핑
- [x] retain_async=True 타임아웃 해결
- [x] Python SDK 전환, JSONL 로깅
- [x] **State 필터링 수정**: relics, potions가 state에서 제거되고 있어 AI가 인지 못 함 → `NOISE_KEYS`에서 제거, 시스템 프롬프트에 안내 추가

## 발견한 것들

### recall은 쿼리를 거의 반영하지 않는다
`DEFECT frost orb`로 검색해도 Ironclad 기억만 나옴. `shop gold`로 검색해도 전투 기억만 나옴.
원인: 뱅크가 78개뿐이고 전부 비슷한 내용. recall이 사실상 뱅크 전체 덤프.

### retain은 전투 play-by-play에 치우쳐 있다
28개 retain 중 93%가 전투 설명. 이벤트 선택, 경로 결정, 캠프파이어, 상점, 빌드 결정 이유 같은 전략적 기억이 거의 없음.
같은 전투에 3~4번 retain해서 중복도 심함.

### state 필터링이 relics/potions를 숨기고 있었다
`cli.py`의 `filter_game_state`가 `NOISE_KEYS = {"deck", "relics", "potions", "map"}`로
모든 state 응답에서 이 필드들을 제거 중. AI가 유물/포션을 전혀 인지하지 못함.
전용 툴(`deck`, `relics`, `potions`, `map`)이 있지만 1,600회 중 40회만 호출,
현재 런에서는 0회.

해결: `relics`, `potions`를 `NOISE_KEYS`에서 제거. `deck`은 combat_state로 카드 정보가
이미 오니까 유지, `map`은 크니까 필요 시 전용 툴로. 시스템 프롬프트에
"State awareness" 섹션 추가.

### reasoning은 recall보다 game state에 의존한다
reasoning 내용 분석 결과, recall 개념이 reasoning에 등장해도 그건 현재 덱에 있는 카드 이름일 뿐.
LLM은 recall 텍스트보다 state JSON을 직접 보고 판단.

### messages 구조
```
[system]  게임 규칙
[user]    State: {게임 state JSON} + Relevant memories: {recall 결과}
[assistant]  tool_calls: [send_command, retain, ...]
[tool]    실행 결과
```
`_handle_send_command`가 tool result 다음에 새 user message를 끼워넣어서 recall 주입.
표준 OpenAI 툴 사이클(user→assistant→tool→assistant)과 다르지만, 의도된 설계.

### crof.ai 524 에러와 OpenAI SDK 재시도
LLM 추론이 길어지면 crof.ai 앞단 Cloudflare가 524 (origin timeout)를 던짐.
OpenAI Python SDK가 내부적으로 감지하고 자동 재시도. 로그에 `Retrying request to
/chat/completions in X.XXX seconds`로 남음. 보통 1~2회 재시도로 해결.

시간 기반 모니터링으로 확인하는 법:
```bash
jq -r 'select(.ts >= "2026-05-02T08:39" and .ts <= "2026-05-02T08:42") |
  "[\(.ts | .[11:19])] [\(.logger)] \(.msg)"' ~/.sts/logs/ai.jsonl
```

## 할 일

### 지금
1. [ ] 현재 런 사망 후 recall/reasoning 재분석
2. [ ] `hindsight bank consolidate sts-v2`로 observation 재생성

### 다음
3. [ ] 다양한 클래스/빌드로 런 돌려서 뱅크 확장
4. [ ] retain 다양화: 비전투 결정(이벤트, 상점, 경로, 캠프파이어)도 기록
5. [ ] Tags 도입 (class, topic, enemy)
6. [ ] recall diversity 옵션 실험 (max_tokens, budget)

### 나중
7. [ ] Reflect로 전략 조언
8. [ ] Mental model 생성
9. [ ] 심장 클리어

## 아키텍처

### 패키지
| 패키지 | 진입점 | 역할 |
|--------|--------|------|
| `packages/ai` | `uv run ai` | LLM 루프. OpenAI 호환 API로 tool-calling. subprocess로 game CLI 호출 |
| `packages/game` | `uv run game <cmd>` | Typer CLI. proxy HTTP(8766)와 통신. Hindsight Python SDK 사용 |
| `packages/proxy` | `uv run proxy` | FastAPI HTTP 서버(8766) + WebSocket 클라이언트. SQLite로 command_id 관리 |
| `packages/bridge` | `uv run bridge` | WebSocket 서버(8765). CommunicationMod stdin/stdout 브리지 |
| `packages/tools` | `uv run tools` | 개발 헬퍼 (게임과 무관) |

### 데이터 흐름
```
AI → subprocess game CLI → httpx proxy(8766) → websocket bridge(8765) → stdin → CommunicationMod → Slay the Spire
```

### 핵심 파일
- `packages/ai/src/ai/main.py` — AI 루프, 툴 정의, 시스템 프롬프트
- `packages/game/src/game/cli.py` — 게임 CLI, Hindsight SDK 호출
- `packages/proxy/src/proxy/main.py` — HTTP 서버 + WebSocket 클라이언트
- `packages/bridge/src/bridge/main.py` — WebSocket 서버 + stdin/stdout 브리지

## Hindsight

소스코드: `/Users/harry/repo/nailed-it/external/hindsight/`

### 발견한 버그: CLI/DB 스키마 불일치
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

# 최근 이벤트 (정상: llm_call → llm_response → tool_call 순환)
tail -3 ~/.sts/logs/ai.jsonl | jq -r '"[\(.event)] \(.msg)"'

# 에러 확인
jq 'select(.lvl == "ERROR") | {ts, msg}' ~/.sts/logs/ai.jsonl | tail -5

# reasoning.jsonl 증가 체크
wc -l ~/.sts/logs/reasoning.jsonl

# AI 멈춤 감지: 최근 이벤트 ts 확인 후 2분 이상 무반응이면 의심 (LLM 호출 평균 19초, 최대 166초)
jq -r '.ts' ~/.sts/logs/ai.jsonl | tail -1
```

### 로그
| 경로 | 내용 | 포맷 |
|------|------|------|
| `~/.sts/logs/ai.jsonl` | AI 결정, 툴 호출, LLM 응답 | JSONL |
| `~/.sts/logs/game.jsonl` | 게임 CLI, Hindsight 호출 | JSONL |
| `~/.sts/logs/reasoning.jsonl` | recall↔reasoning 쌍 | JSONL |
| `~/.sts/logs/llm_dump/` | LLM 호출 직전 messages | JSON (최근 10개) |
| `~/.sts/logs/proxy.log` | proxy 연결, 타임아웃 | 텍스트 |
| `~/.sts/logs/bridge.log` | stdin/stdout 프로토콜 | 텍스트 |
| `~/.sts/logs/runs.log` | 런 종료 시 전체 상태 | 텍스트 |

모두 RotatingFileHandler(10MB×5). `jq`로 필터링 가능.

### 알려진 이슈
- **메시지 트리밍**: 1MB 초과 시 오래된 턴부터 드롭. system message는 보존.
- **LLM 재시도**: SDK 재시도 꺼짐(max_retries=0). 앱 레벨에서 exponential backoff로 처리 (524, 500, 429, connection error).
- **런 종료**: `in_game=false` → runs.log 기록 + retain 유도.
- **retain/recall 동일 턴 금지**: retain은 write, recall은 read. indexing 시간 필요.
- **START 직후 오탐지**: 새 런 시작 시 `in_game=null`을 run_end로 착각해 불필요한 retain 발생.

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
