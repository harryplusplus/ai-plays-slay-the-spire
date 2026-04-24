# AI 에이전트 노트 — Slay the Spire

## 프로젝트 개요
LLM(glm-5.1 via Ollama Cloud)이 Slay the Spire를 CommunicationMod를 통해 자동으로 플레이하는 봇.

## 목적
1. **심장(Heart) 클리어** — 승천 0, 심장 클리어가 최종 목표
2. **학습 가능한 AI** — 각 런에서 배운 전략, 패턴, 교훈을 Hindsight 장기기억에 축적하여 다음 런에 활용
3. **지속적 개선** — retain/recall 사이클을 통해 시간이 지날수록 플레이 품질 향상

## 문서화 메타: 이 파일과 README를 어떻게 다루는가

### 이 문서(AGENTS.md)의 역할
- **실행 레퍼런스 + 현재 상황판**: 우리가 작업할 때 뭘 재시작해야 하는지, 현재 어떤 문제가 있는지, 다음에 뭘 할지를 확인하는 기준
- **협업 공유 문서**: Harry와 AI 에이전트가 모두 읽고 참고하며, 작업 결과를 바탕으로 함께 업데이트하는 살아있는 문서
- **상황 인식 도구**: 프로젝트의 현재 상태, 시도한 것, 배운 것, 다음 단계를 기록하여 의사결정의 일관성 유지

### README.md의 역할
- **프로젝트의 얼굴**: 외부(또는 미래의 나)가 볼 때 이 프로젝트가 뭔지, 왜 특별한지, 어떻게 협업하는지
- **메타인지 기록**: 기술 설명서가 아니라 "우리가 무엇을 하며 어떻게 배워가는가"에 대한 기록
- **협업 철학**: Harry와 AI 에이전트의 역할 분담, 의사결정 방식

### 문서화 개선 역사
1. **초기**: 간단한 AI 에이전트 노트 (기능 목록 중심)
2. **코드 기준 사실 바로잡기**: README와 AGENTS.md가 실제 코드와 달랐음 → 코드를 직접 읽고 구조/데이터 흐름 정확히 기술
3. **메타인지 전환**: 기술 설명서 → "우리가 무엇을 하며 무엇을 배우는가" 기록
4. **역할 분담 명시**: "Harry는 뭘 하고 AI는 뭘 하는가" 명확히 기술
5. **현재 상황 중심 재구조화**: "문제 → 해결 → 다음" 흐름으로 정리

### 문서화 원칙 (앞으로 지킬 것)
- **코드와 문서 불일치 시 코드가 우선**: 문서가 코드보다 앞서가지 않도록. 코드 변경 후 문서 즉시 업데이트
- **"우리" 중심 서술**: "AI가~"가 아니라 "우리가~". 협업 과정 자체를 기록
- **구체적 예시 포함**: "의미있는 기억"같은 추상적 표현보다 실제 retain 예시를 before/after로 보여주기
- **살아있는 로드맵**: `[x]` 완료, `[~]` 진행 중, `[ ]` 미완료로 명확히 표시
- **AGENTS.md는 한국어**: Harry가 읽는 문서이므로 한국어로 유지
- **README는 한국어 + Harry 명시**: "Harry"라는 이름을 명확히 사용, AI 에이전트가 작성 중임을 고지

## 현재 상황 (2026-04-24 ~ 진행 중)

### 최근 변경사항

#### cli_v2.py 작성 + Python SDK 전환
- `packages/game/src/game/cli_v2.py` 신규 작성
- Hindsight Python SDK(`hindsight-client`) 사용, subprocess CLI 호출 제거
- `game` 진입점을 `cli_v2:main`으로 전환, `game-v2`는 동일 대상

#### 로그 포맷 JSONL 전환
- `game.jsonl` (`~/.sts/logs/game.jsonl`): `cli_v2.py`의 모든 이벤트를 JSON Lines로 기록
- `ai.jsonl` (`~/.sts/logs/ai.jsonl`): `ai/main.py`의 모든 이벤트를 JSON Lines로 기록
- `proxy.log`, `bridge.log`는 텍스트 유지 (변경 없음)
- 이벤트 필드: `event`, `tool`, `arguments`, `state` 등으로 `jq` 필터링 가능

#### sts-v2 bank 생성 및 마이그레이션
- `sts` bank의 저품질 메모리(상태 스냅샷)를 제외하고, 2026-04-24 09:00 UTC 이후 고품질 메모리 101개를 `sts-v2`로 이전
- `sts-v2` 현재 상태: ~192 memory units, EXPERIENCE/OBSERVATION 중심

#### retain_async=True로 타임아웃 해결
- Python SDK `retain()`은 기본 `retain_async=False`로 서버가 작업 완료까지 blocking
- 이를 `retain_batch(retain_async=True)`로 변경하여 즉시 반환, 백그라운드 worker 처리
- async 변경 후 retain timeout **0건**

#### operation_id 로깅
- async retain 반환 시 `operation_id`를 `game.log`에 기록
- 향후 worker 실패 추적 가능

### 우리가 기대하는 것
- **의미있는 기억 축적**: "에너지 2→1" 같은 상태 스냅샷이 아니라, "Chosen은 Hex로 Dazed를 부여하니 빠른 딜이 필요했다" 같은 전략적 교훈
- **Hindsight Observation 형성**: 시간이 지나면서 durable pattern이 관찰되길 기대. 예: "Frost 오브 빌드는 Act 2에서 안정적"
- **Recall 품질 향상**: 의미있는 기억이 쌓이면, recall 시 전략적 조언이 늘어나야 함

### 우리가 한 작업 (완료)

#### 1단계: Retain 빈도 제한
- `send_command` 직후 강제 retain 메시지 제거
- `END` 턴 종료 시에만 retain 강제
- 개별 `PLAY`/`STATE`/etc 후에는 retain 유도하지 않음

#### 2단계: Retain 내용 가이드라인 강화
- System prompt에 "전략적 결정, 패턴, 교훈 중심" 명시
- raw HP/energy/block 나열 금지
- retain 툴 description 개선: "WHY와 WHAT was learned, not raw numbers"

#### 3단계: Hindsight Bank 설정
- `hindsight bank mission sts-v2`로 retain_mission 설정:
  > "Extract strategic decisions, build directions, enemy patterns and weaknesses, card synergies discovered, and combat lessons learned..."
- `hindsight bank set-config sts-v2`로 observations_mission 설정:
  > "Identify recurring build strategies, enemy vulnerability patterns, and effective card combinations..."
- `game/cli.py`의 `RETAIN_CONTEXT` 개선

#### 4단계: Retain 포맷 템플릿
- END 후 user message에 구체적 템플릿 제공:
  - Situation: [enemy/room and key patterns]
  - Decision: [what you did and why]
  - Outcome: [what worked, 1-2 sentences]
  - Lesson: [remember for next time]

### 결과: 품질 개선 확인됨

**이전 retain 예시** (문제):
> "에너지 2→1, Chosen HP 47→41, 손패: Loop, Dualcast+, Strike..."

**현재 retain 예시** (개선됨):
> "Against the Act 2 bandit encounter (Pointy/Romeo/Bear), Electro + Lightning orb passives were extremely effective... Red Mask is an excellent relic pickup for this build since it applies Weak to all enemies at combat start, synergizing perfectly with Electro's AoE lightning."

> "Situation: Turn 1 against Spheric Guardian, which opens with 40 block, Barricade, and 2 Artifact. Decision: Played Electrodynamics to enable lightning AoE... Lesson: Against Barricade enemies like Spheric Guardian, sustained orb damage is key..."

- 템플릿 포맷(Situation/Decision/Outcome/Lesson) 따르는 retain 확인됨
- 시너지 분석, 빌드 방향, 적 패턴 분석 포함됨
- raw 숫자 나열 사라짐

### 로그 현황
- `game.jsonl` — `event`: `command`/`recall`/`recall_result`/`retain`
- `ai.jsonl` — `event`: `init`/`llm_call`/`llm_response`/`tool_call`/`tool_result`/`auto_recall`/`message_trim`/`run_end`
- `jq` 필터링 가능: `jq 'select(.event == "tool_call" and .tool == "send_command") | .arguments.command'`

### 현재 Hindsight Bank 상태
- **`sts-v2` bank** (현재 사용 중): **285 memory units**, **114개 documents**
  - EXPERIENCE 85개, OBSERVATION 97개, WORLD 18개
  - 고품질 메모리만 축적 (2026-04-24 09:00 UTC 이후)
- `sts` bank (레거시, 더 이상 사용 안 함): 628개 memory units

### 모니터링 결과

#### Retain
- async 변경 후 **타임아웃 0건** (20:17 이후)
- retain 품질: Situation/Decision/Outcome/Lesson 템플릿 준수율 높음
- **END 후 retain 누락 패턴**: **실제 누락 0건** — 이전 분석에서 "END 후 다음 커맨드까지 retain 없음"을 누락으로 봤으나, 그 사이에 전투가 계속된 경우(다음 턴 PLAY/END/WAIT)도 포함됐던 것. 전투 종료 후 COMBAT_REWARD/MAP 도달 시에는 모두 retain 있음.

#### Recall
- **정상 작동**하나 응답 지연 심함: **~26초** (embedding 5s + reranking 21s)
- 원인: OpenClaw bank의 batch_retain 작업과 Hindsight worker 리소스 경쟁
- 현재 116 facts / 4059 tokens 반환 — context 과다 가능성
- 기능적으로는 문제없으나 전체 턴 시간 증가

#### Async Retain 추적
- `operation_id` 로깅 추가됨
- worker 실패 시 메모리 유실 가능성 있으나, 현재까지 누적 증가 확인

## 과거 문제 (참고)

처음에는 프롬프트가 "매 커맨드 후 retain"을 강제해서 한 턴에 4번 retain이 쌓였다. 내용은 대부분 "에너지 2→1" 같은 순간 상태 스냅샷. Hindsight fact extraction이 이를 EXPERIENCE/OBSERVATION으로 분해 저장했으나, 원본 fact 자체가 의미없어서 Observation도 의미없는 noise만 축적됨.

원인:
1. Retain 빈도 과다: 매 커맨드 후 retain → 한 턴에 4번
2. Retain 내용 부실: 상태 변화 나열, 전략/교훈 부재
3. Hindsight mission 미설정: `retain_mission`이 null
4. Context field 부실: `"Slay the Spire gameplay"`만으로는 extraction 방향 불충분

## 앞으로 항상 염두에 둘 원칙

### 의미있는 기억의 기준
| 의미있는 정보 | 의미없는 정보 |
|--------------|--------------|
| "Act 2 Chosen vs Frost 오브 + Dualcast 콤보. Hex 패턴 확인 후 빠른 딜로 안정 클리어" | "에너지 2→1, Chosen HP 47→41" |
| "Claw pickup으로 0-cost 스택 빌드 시도. Reprogram 대신 Hologram 선택 (오브 중심)" | "손패: Loop, Dualcast+, Strike, Electrodynamics" |
| "Chosen은 턴 단위 Hex(6 Dazed). 단일 타겟 높은 딜 선호" | "턴 3, energy 2, block 0" |
| "Electrodynamics early pick 후 energy 부족. Act 1에서는 energy 효율 카드 우선" | "Zap 플레이, Lightning 패시브 3딜" |

### Hindsight 관찰 시스템 이해
- **Observation** = 시간이 지나면서 여러 fact가 누적되어 형성되는 **durable pattern**
- Observation은 이전 기억의 강도를 보정해주지만, **원본 fact 자체가 의미있어야** 의미있는 Observation이 생김
- **Context field는 high-impact** — extraction 방향을 결정
- **Retain과 recall을 같은 턴에 하지 말 것** — retain은 write, recall은 read. 쓴 것은 다음 턴에야 검색 가능

## 다음에 할 것

### 단기 (지금 바로 또는 몇 런 내)
1. **Retain 품질 지속 모니터링** — 몇 런 더 돌려보고 템플릿 준수율, 전략적 내용 비율 확인
2. **Hindsight consolidation trigger** — `hindsight bank consolidate sts-v2`로 observation 재생성, 새로운 fact 기반으로 observation 업데이트
3. **Recall 품질 확인** — recall 결과에 실제로 전략적 조언이 포함되는지 확인

### 중기 (다음 런들에서)
4. **Tags 활용 검토** — `topic:combat`, `topic:build`, `topic:event` 등으로 분류하면 검색 품질 향상 가능성
5. **Entity labels 도입** — `enemy_name`, `act`, `card_type` 등으로 정형화
6. **Mental model 생성** — 직업별 빌드 가이드, Act별 적 대응 전략 등 reflect 결과를 mental model로 고정

### 장기 (목표 달성 과정)
7. **Reflect 활용** — 단순 recall이 아닌 Hindsight reflect로 전략 조언 받기
8. **Budget 조정** — `recall_budget_function`을 `adaptive`로 변경해 검색 깊이 동적 조절
9. **심장 클리어**

## 패키지 구조 (실제)

| 패키지 | 진입점 | 역할 |
|--------|--------|------|
| `packages/ai` | `uv run ai` | LLM 에이전트 루프. OpenAI 호환 API. `subprocess`로 `game` CLI를 호출함. |
| `packages/game` | `uv run game <cmd>` | Typer CLI. 서브커맨드: `command`, `deck`, `relics`, `potions`, `map`, `recall`, `retain`. proxy HTTP(8766)와 통신. `recall`/`retain`은 Hindsight Python SDK를 사용. |
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
- `packages/game/src/game/cli_v2.py` — 게임 CLI (proxy 클라이언트 + Hindsight Python SDK 호출)
- `packages/proxy/src/proxy/main.py` — HTTP 서버 + WebSocket 클라이언트 + SQLite
- `packages/bridge/src/bridge/main.py` — WebSocket 서버 + stdin/stdout 브리지

## Hindsight 소스코드

Hindsight는 `/Users/harry/repo/nailed-it/external/hindsight/`에 위치하며, 이 프로젝트와는 별도의 저장소다. 우리는 Hindsight의 소스코드를 직접 읽고 분석할 수 있다.

### 핵심 패키지

| 패키지 | 언어 | 역할 |
|--------|------|------|
| `hindsight-api-slim/` | Python/FastAPI | API 서버. retain/recall/reflect 로직, DB 스키마, 마이그레이션 |
| `hindsight-cli/` | Rust | CLI 도구. `hindsight memory recall` 등의 명령어 처리 |

### 중요한 발견: CLI 코드가 DB 스키마보다 outdated

우리가 직접 소스코드를 조사해서 발견한 핵심 버그:

**DB 스키마 (최신)** — `hindsight-api-slim/hindsight_api/alembic/versions/g2h3i4j5k6l7_remove_opinion_fact_type.py` (2026-04-02):
```sql
CHECK (fact_type IN ('world', 'experience', 'observation'))
```
- `opinion` 타입이 **완전 제거됨**
- `observation` 타입이 **추가됨** (consolidation 결과)

**CLI 코드 (구식)** — `hindsight-cli/src/main.rs`:
```rust
default_values = &["world", "experience", "opinion"]
```
- 여전히 `opinion`을 기본값으로 사용
- `observation`이 **기본값에 없음**

**결과**: `hindsight memory recall` 기본 호출 시 `observation` 타입 메모리가 검색 결과에서 **제외됨**. 우리가 개선한 고품질 기억이 consolidate되어 `observation`으로 생성되었으나, recall로는 검색되지 않는 치명적 불일치.

**해결**: `game/cli.py`에서 `--fact-type world --fact-type experience --fact-type observation`을 명시적으로 전달하여 CLI의 구식 기본값을 우회.

이것이 우리가 소스코드를 직접 읽어야만 발견할 수 있었던 버그다.

## 환경변수

| 변수 | 필요한 패키지 | 설명 |
|------|--------------|------|
| `OLLAMA_API_KEY` | `ai` | LLM API 키 (Ollama Cloud) |

## 서비스 실행 워크플로우 (tmux)

### 세션 구조

| 세션명 | 역할 | 재시작 필요 시점 |
|--------|------|-----------------|
| `sts-ai` | AI 에이전트 루프 | `packages/ai` 코드 변경 시 |
| `sts-proxy` | Proxy 서버 | `packages/proxy` 코드 변경 시 |
| `hs-api` | Hindsight API 서버 | Hindsight 관련 작업 시 (건드리지 않음) |
| `hs-web` | Hindsight 웹 UI | Hindsight 관련 작업 시 (건드리지 않음) |

### 재시작 절차 (반드시 사용자 승인 후 실행)

```
1. 현재 상태 확인
   → tmux ls
   → tail -20 ~/.sts/logs/ai.jsonl

2. 사용자에게 제안
   "<세션명> 재시작이 필요합니다. 명령어: ..."

3. 사용자 승인 대기
   → "승인" 또는 "응" 등 긍정적 응답 확인

4. 재시작 실행
   tmux kill-session -t <세션명>
   tmux new-session -d -s <세션명> -c <워크디렉토리> "<명령어>"

5. 정상 기동 확인
   → tmux ls
   → 로그 tail로 초기화 확인
```

### 주의사항
- `hs-api`, `hs-web` 세션은 **절대 건드리지 않음**
- `kill-server`는 사용하지 않음 (다른 프로젝트 세션 영향)
- 환경변수 변경 시 `.bashrc` 수정 → tmux 서버 재시작 필요 (서버가 Apr 20 이후 유지 중)

## 알려진 이슈 / 주의사항

- **메시지 트리밍**: 총 메시지 문자 수가 400K 초과 시 오래된 완전 턴(assistant+tool+user)을 드롭. 시스템 메시지는 보존.
- **LLM 재시도**: API 실패 시 10초 후 재시도.
- **런 종료**: `in_game=false` 감지 시 `~/.sts/logs/runs.log`에 전체 상태 기록 + "retain 후 새 게임 시작" 유도.
- **프록시 타임아웃**: 30초. 브리지 재연결은 자동.
- **Retain/recall 동일 턴 금지**: Hindsight는 write 후 indexing에 시간이 걸림. retain 후 바로 recall핏 사이 새로운 메모리가 안 뜰 수 있음.

## 로그 위치

| 경로 | 목적 |
|------|------|
| `~/.sts/logs/ai.jsonl` | AI 결정, 툴 호출, LLM 응답 (JSON Lines) |
| `~/.sts/logs/game.jsonl` | 게임 CLI 호출, Hindsight 호출 (JSON Lines) |
| `~/.sts/logs/proxy.log` | command_id, 브리지 재연결, 타임아웃 (텍스트) |
| `~/.sts/logs/bridge.log` | stdin/stdout 프로토콜 메시지 (텍스트) |
| `~/.sts/logs/runs.log` | 런 종료 시 전체 상태 (텍스트) |
| `~/.sts/proxy.db` | SQLite command_id 카운터 |

모든 로그는 RotatingFileHandler(10MB, 5 백업) 사용.
