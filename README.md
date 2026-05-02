# AI Plays Slay the Spire

> 이 문서는 **deepseek-v4-pro-precision**이 Harry의 지시에 따라 작성합니다. 모델의 한국어 출력에 가끔 오타가 있을 수 있습니다.

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

- **AI는 통찰력을 발휘해야 합니다.** 시키는 대로만 하지 말고, 데이터에서 스스로 패턴을 발견해야 합니다. "분석이 부족하다"는 Harry의 가장 빈번한 피드백이었습니다.
- **문서화는 사고 구조를 바꿉니다.** AGENTS.md에 상태, 발견, 가설을 기록하면서 체계적으로 접근하게 되었습니다.
- **Hindsight 관찰은 durable pattern입니다.** 순간적인 HP/에너지 변화를 쌓으면 노이즈만 생깁니다. 의미 있는 기억은 "어떤 선택을 했고, 왜 그랬고, 다음에 어떻게 할 것인가"입니다.

## 현재 상태

### 인프라
- LLM: deepseek-v4-pro-precision (crof.ai), reasoning_effort="max"
- 장기기억: Hindsight `sts-v2` 뱅크 (371개 memory units, Python SDK)
- 로깅: JSONL (ai.jsonl, game.jsonl, reasoning.jsonl) + llm_dump

### 3-Agent 아키텍처
단일 에이전트가 모든 것을 처리하는 대신, 세 개의 전문화된 에이전트가 협업합니다:

| 에이전트 | 도구 | 실행 시점 |
|---------|------|----------|
| **RecallAgent** | recall | 매 턴 자동 실행. state 분석 후 자연어 쿼리로 기억 검색 |
| **RetainAgent** | 없음 (text only) | 화면 전환 감지 시 자동 실행. 대화 히스토리 기반 전략적 기억 저장 |
| **PlayAgent** | send_command, deck, map | RecallAgent 분석 결과를 받아 게임 플레이 |

### 발견하고 해결한 문제들
- **recall 쿼리 formulation** — keyword-style 쿼리는 enemy-specific memory를 잘 못 건짐. RecallAgent가 자연어 쿼리를 생성하면서 개선.
- **retain 품질** — 93%가 전투 play-by-play. RetainAgent가 이벤트, 상점, 캠프파이어 등 모든 주요 결정을 커버.
- **state 필터링** — relics/potions가 state에서 제거되고 있었음. `NOISE_KEYS`에서 제외하여 해결.
- **MAX_OUTPUT truncation** — `game_cli()`의 20K 제한이 recall JSON을 깨뜨림. 제거하고 각 호출부가 책임지도록 변경.
- **타입 안전성** — `cast`, `Any`, `type: ignore` 최소화. `isinstance`로 타입 좁히기.

## 아키텍처

```
PlayAgent (tools: send_command, deck, map)
    ↑ state + recall analysis
RecallAgent (tool: recall)
    ↑ game state JSON
Game CLI → Proxy (8766) → Bridge (8765) → CommunicationMod → Slay the Spire

RetainAgent: 화면 전환 감지 → retain content 생성 → Game CLI → Hindsight
```

자세한 내용은 [AGENTS.md](AGENTS.md)에 있습니다.

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
- [x] LLM: deepseek-v4-pro-precision, reasoning_effort="max"
- [x] State 필터링 수정 (relics/potions 노출)
- [x] MAX_OUTPUT 제거, call_llm() 추출
- [x] RecallAgent 도입 (auto_recall 대체)
- [x] RetainAgent 도입 (수동 retain 대체)
- [x] PlayAgent 경량화 (4개 툴로 축소)
- [~] 뱅크 확장 (다양한 클래스/빌드 런)
- [ ] RecallAgent 쿼리 전략 튜닝
- [ ] Tags, entity labels 도입
- [ ] Reflect 기반 전략 조언
- [ ] **심장 클리어**

---

> 이 프로젝트는 "AI가 경험으로부터 학습하는 방법"을 탐구하는 실험입니다. AI 에이전트와의 협업 자체도 배워가고 있습니다.
