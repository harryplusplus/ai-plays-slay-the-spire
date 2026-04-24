# AI 에이전트 노트 — Slay the Spire

## 프로젝트 개요
LLM(kimi-k2.6 via OpenCode)이 Slay the Spire를 CommunicationMod를 통해 자동으로 플레이하는 봇.

## 목적
1. **심장(Heart) 클리어** — 승천 0, 디펙트로 심장 클리어가 최종 목표
2. **학습 가능한 AI** — 각 런에서 배운 전략, 패턴, 교훈을 Hindsight 장기기억에 축적하여 다음 런에 활용
3. **지속적 개선** — retain/recall 사이클을 통해 시간이 지날수록 플레이 품질 향상

## 현재 문제: 기억 시스템의 Noise 축적

### 문제 본질
Hindsight의 **Observation**은 "여러 사실이 시간이 지나면서 누적되어 형성되는 durable pattern"이다. Observation 시스템은 사실의 변경을 추적하고 이전 기억의 강도를 보정해주지만, **쌓는 정보 자체가 의미있어야** 의미있는 Observation이 생긴다.

현재 AI가 본문으로 본내는 retain content가 "에너지 2→1", "Chosen HP 47→41" 같은 **순간 상태 스냅샷**이라서, Hindsight fact extraction이 이를 의미없는 EXPERIENCE/OBSERVATION으로 분해 저장하고 있다. 결과적으로 529개 memory unit 중 학습 가치 있는 정보가 매우 적다.

### 문제 증상
- `sts` bank: 529개 memory units, 72개 documents, 21,810개 links
- EXPERIENCE 268개, OBSERVATION 218개, WORLD 43개
- 대부분이 한 턴 내 3~4개의 retain이 연속으로 쌓인 결과
- 동일 `chunk_id`에 여러 메모리가 묶여 있으나 내용이 상태 변화 나열

### 원인 분석
1. **Retain 빈도 과다**: 프롬프트가 "매 커맨드 후 retain"을 강제 → 한 턴에 4번 retain
2. **Retain 내용 부실**: AI가 상태 변화(HP, 에너지, 블록)를 나열하지만 전략/교훈은 부재
3. **Hindsight mission 미설정**: `retain_mission`이 null이라 Hindsight가 "뭐를 추출할지"를 몰라서 모든 것을 추출
4. **Context field 부실**: `context="Slay the Spire gameplay"`만으로 extraction 방향 제시 불충분

## 우리가 시도한 것들

### 1단계: Retain 빈도 제한 (완료)
- `send_command` 직후 강제 retain 메시지 제거
- `END` 턴 종료 시에만 retain 강제
- 개별 `PLAY`/`STATE`/etc 후에는 retain 유도하지 않음

### 2단계: Retain 내용 가이드라인 강화 (완료)
- System prompt에 "전략적 결정, 패턴, 교훈 중심" 명시
- raw HP/energy/block 나열 금지
- retain 툴 description 개선: "WHY와 WHAT was learned, not raw numbers"

### 3단계: Hindsight Bank 설정 (완료)
- `hindsight bank mission sts`로 retain_mission 설정:
  > "Extract strategic decisions, build directions, enemy patterns and weaknesses, card synergies discovered, and combat lessons learned. Ignore raw state snapshots like HP, energy, block numbers, and individual card play sequences. Focus on what the player chose and why, and what patterns emerged from the outcome."
- `hindsight bank set-config sts`로 observations_mission 설정:
  > "Identify recurring build strategies, enemy vulnerability patterns, and effective card combinations. Track evolving deck archetypes and success/failure patterns across runs. Highlight contradictions between expected and actual outcomes."
- `game/cli.py`의 `RETAIN_CONTEXT` 개선

### 4단계: Retain 포맷 템플릿 (완료)
- END 후 user message에 구체적 템플릿 제공:
  - Situation: [enemy/room and key patterns]
  - Decision: [what you did and why]
  - Outcome: [what worked, 1-2 sentences]
  - Lesson: [remember for next time]

## 앞으로 항상 염두에 둘 원칙

### 의미있는 기억의 기준
StS 플레이에서 의미있는 정보는 "어떤 선택을 했고 어떤 결과가 나왔고 나중에 참고할만한 수준의 정보"다:

| 의미있는 정보 | 의미없는 정보 |
|--------------|--------------|
| "Act 2 Chosen vs Frost 오브 + Dualcast 콤보. Hex 패턴 확인 후 빠른 딜로 안정 클리어" | "에너지 2→1, Chosen HP 47→41" |
| "Claw pickup으로 0-cost 스택 빌드 시도. Reprogram 대신 Hologram 선택 (오브 중심)" | "손패: Loop, Dualcast+, Strike, Electrodynamics" |
| "Chosen은 턴 단위 Hex(6 Dazed). 단일 타겟 높은 딜 선호" | "턴 3, energy 2, block 0" |
| "Electrodynamics early pick 후 energy 부족. Act 1에서는 energy 효율 카드 우선" | "Zap 플레이, Lightning 패시브 3딜" |
| "Act 2 Elite 전 Hoarder 유물 획득. 덱 두께 35장으로 회전율 저하" | "gold 228, HP 74/75" |

### Hindsight 관찰 시스템 이해
- **Observation** = 시간이 지나면서 여러 fact가 누적되어 형성되는 **durable pattern**
- Observation은 이전 기억의 강도를 보정해주지만, **원본 fact 자체가 의미있어야** 의미있는 Observation이 생김
- **Pre-summarizing before retain은 anti-pattern** — raw content를 retain해야 extraction quality가 높아짐 (하지만 우리는 AI가 이미 요약해서 본냄. 이것은 어쩔 수 없는 제약)
- **Context field는 high-impact** — extraction 방향을 결정
- **document_id는 stable해야 함** — random UUID는 duplicate 생성
- **Retain과 recall을 같은 턴에 하지 말 것** — retain은 write, recall은 read. 쓴 것은 다음 턴에야 검색 가능

## 앞으로 시도핳 후보

### 단기
1. **새로운 retain 정책 효과 모니터링** — 몇 런 돌려보고 memory unit 품질 확인
2. **Hindsight consolidation trigger** — `hindsight bank consolidate sts`로 observation 재생성
3. **Mental model 생성** — "디펙트 빌드 가이드", "Act 1/2/3 적 대응 전략" 등

### 중기
4. **Tags 활용** — `topic:combat`, `topic:build`, `topic:event` 등으로 분류하면 검색 품질 향상
5. **Entity labels** — `card_type`, `enemy_name`, `act` 등으로 정형화
6. **Delta/Apppend 모드** — 한 런의 메모리를 하나의 document로 관리

### 장기
7. **Reflect 활용** — 단순 recall이 아닌 Hindsight reflect로 전략 조언 받기
8. **Budget 조정** — `recall_budget_function`을 `adaptive`로 변경해 검색 깊이 동적 조절

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
