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
- 장기기억: Hindsight `sts-v2` 뱅크 (Python SDK)
- 로깅: JSONL (ai.jsonl, game.jsonl, reasoning.jsonl) + llm_dump

### 발견한 문제들
- **recall이 쿼리를 반영하지 못함** — 뱅크가 78개로 작고 전부 비슷한 내용. 쿼리가 달라도 같은 결과 반환.
- **retain이 전투 설명에 치우침** — 이벤트, 상점, 경로 선택 같은 전략적 결정 기록 부족.
- **reasoning은 recall보다 game state에 의존** — LLM이 state JSON을 직접 보고 판단.

### 진행 중
- 더 많은 런으로 뱅크 확장 중
- recall diversity 개선 방안 탐색 중

## 아키텍처

```
AI (packages/ai) → Game CLI (packages/game) → Proxy (packages/proxy)
                                                       ↓ WebSocket
                                                 Bridge (packages/bridge)
                                                       ↓ stdin/stdout
                                            CommunicationMod (Java mod)
                                                       ↓
                                              Slay the Spire
```

AI는 tool-calling 방식으로 게임을 제어합니다. 매 턴 Hindsight에서 recall한 기억을 컨텍스트에 주입하고, 턴 종료/전투 종료 시 retain으로 기억을 저장합니다.

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
- [x] Retain 품질 개선 (템플릿, 타이밍, mission 설정)
- [x] Python SDK 전환, JSONL 로깅
- [x] reasoning.jsonl (recall↔reasoning 분석 인프라)
- [x] LLM: deepseek-v4-pro-precision, reasoning_effort="max"
- [~] 뱅크 확장 (다양한 클래스/빌드 런)
- [ ] Recall diversity 개선
- [ ] Retain 다양화 (비전투 결정 포함)
- [ ] Tags, entity labels 도입
- [ ] Reflect 기반 전략 조언
- [ ] **심장 클리어**

---

> 이 프로젝트는 "AI가 경험으로부터 학습하는 방법"을 탐구하는 실험입니다. AI 에이전트와의 협업 자체도 배워가고 있습니다.
