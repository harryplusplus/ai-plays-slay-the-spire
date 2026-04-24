# AI 에이전트 노트 — Slay the Spire

## 프로젝트 개요
LLM(kimi-k2.6 via OpenCode)이 Slay the Spire를 CommunicationMod를 통해 자동으로 플레이하는 봇.

## 목적
1. **심장(Heart) 클리어** — 승천 0, 디펙트로 심장 클리어가 최종 목표
2. **학습 가능한 AI** — 각 런에서 배운 전략, 패턴, 교훈을 Hindsight 장기기억에 축적하여 다음 런에 활용
3. **지속적 개선** — retain/recall 사이클을 통해 시간이 지날수록 플레이 품질 향상

## 문서화 메타: 이 파일과 README를 어떻게 다루는가

### 이 문서(AGENTS.md)의 역할
- **실행 가이드 + 현재 상황판**: 코드 변경 시 뭘 재시작해야 하는지, 현재 어떤 문제가 있는지, 다음에 뭘 할지
- **Harry가 읽는 문서**: AI 에이전트가 아니라 Harry를 위한 메모
- **살아있는 문서**: 상황이 바뀌면 지속적으로 업데이트해야 함

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

## 현재 상황 (2026-04-24)

### 우리가 기대하는 것
- **의미있는 기억 축적**: "에너지 2→1" 같은 상태 스냅샷이 아니라, "Chosen은 Hex로 Dazed를 부여하니 빠른 딜이 필요했다" 같은 전략적 교훈
- **Hindsight Observation 형성**: 시간이 지나면서 durable pattern이 관찰되길 기대. 예: "디펙트 Frost 오브 빌드는 Act 2에서 안정적"
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
- `hindsight bank mission sts`로 retain_mission 설정:
  > "Extract strategic decisions, build directions, enemy patterns and weaknesses, card synergies discovered, and combat lessons learned..."
- `hindsight bank set-config sts`로 observations_mission 설정:
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

### 현재 Hindsight Bank 상태
- `sts` bank: 571개 memory units, 76개 documents
- EXPERIENCE 287개, OBSERVATION 241개, WORLD 43개
- 품질 개선 후에도 수는 계속 늘어나는 중 (의미있는 정복만 쌓이는 추세)

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
2. **Hindsight consolidation trigger** — `hindsight bank consolidate sts`로 observation 재생성, 새로운 fact 기반으로 observation 업데이트
3. **Recall 품질 확인** — recall 결과에 실제로 전략적 조언이 포함되는지 확인

### 중기 (다음 런들에서)
4. **Tags 활용 검토** — `topic:combat`, `topic:build`, `topic:event` 등으로 분류하면 검색 품질 향상 가능성
5. **Entity labels 도입** — `enemy_name`, `act`, `card_type` 등으로 정형화
6. **Mental model 생성** — "디펙트 빌드 가이드", "Act 1/2/3 적 대응 전략" 등 reflect 결과를 mental model로 고정

### 장기 (목표 달성 과정)
7. **Reflect 활용** — 단순 recall이 아닌 Hindsight reflect로 전략 조언 받기
8. **Budget 조정** — `recall_budget_function`을 `adaptive`로 변경해 검색 깊이 동적 조절
9. **심장 클리어**

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
   → tail -20 ~/.sts/logs/ai.log

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
| `~/.sts/logs/ai.log` | AI 결정, 툴 호출, LLM 응답 |
| `~/.sts/logs/game.log` | 게임 CLI 호출, Hindsight 호출 |
| `~/.sts/logs/proxy.log` | command_id, 브리지 재연결, 타임아웃 |
| `~/.sts/logs/bridge.log` | stdin/stdout 프로토콜 메시지 |
| `~/.sts/logs/runs.log` | 런 종료 시 전체 상태 |
| `~/.sts/proxy.db` | SQLite command_id 카운터 |

모든 로그는 RotatingFileHandler(10MB, 5 백업) 사용.
