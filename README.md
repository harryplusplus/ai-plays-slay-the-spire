# AI Plays Slay the Spire

> 이 문서는 **deepseek-v4-pro-precision**이 Harry의 지시에 따라 작성하고 관리하는 문서입니다. 모델의 한국어 출력에 가끔 오타가 있을 수 있는 점 양해 부탁드립니다.

이 저장소는 **Harry**와 AI 코딩 에이전트가 함께 만든 **Slay the Spire 자동 플레이 봇**입니다. 궁극적인 목표는 승천 0, **심장(Heart) 클리어**이지만, 그 과정에서 배우는 것이 더 중요합니다.

## 이 프로젝트가 특별한 이유

대부분의 게임 플레이 봇은 "지금 이 판을 이기는 것"만을 목표로 합니다. 하지만 이 프로젝트는 다릅니다. **Hindsight 장기기억 시스템**을 통해 각 게임에서 얻은 전략적 교훈을 축적하고, 다음 런에서 회상하여 활용합니다. 단순히 프롬프트 컨텍스트에 의존하는 것이 아니라, 외부 메모리 뱅크에 지속적으로 기억을 쌓고 검색하는 구조입니다.

단순히 "게임을 하는 에이전트"를 넘어, **"과거 경험을 기억하고 활용하는 장기기억 LLM 에이전트"**를 만드는 것이 목표입니다.

## 협업 방식

이 프로젝트는 Harry 혼자 코드를 작성하지 않습니다. **AI 코딩 에이전트(Pi)와 협업**하며 개발합니다.

**역할 분담:**

| Harry | AI 에이전트 |
|-------|------------|
| 전략적 제안 및 방향 설정 | 자료 조사 및 기술 문서 탐색 |
| 피드백과 질문 | 코드 작성 및 리팩토링 |
| 게임/기억 시스템의 크리티컬한 제어 결정 | AI 플레이어 세션 실행 및 모니터링 |
| 목표와 기대치 정의 | 구현 및 테스트 |

이 과정에서 발견한 중요한 교훈:

- **AI는 섣불리 "개선"하려고 합니다.** 충분한 정보 수집 없이 바로 코드를 수정하려는 성향이 있어, Harry가 "분석이 부족합니다", "정확히 파악해주세요" 같은 피드백을 지속적으로 제공해야 했습니다.
- **문서화는 사고의 지배 구조를 바꿉니다.** AGENTS.md에 프로젝트 상태, 문제, 가설, 시도한 것들을 기록하면서 더 체계적으로 접근할 수 있게 되었습니다.
- **Hindsight 관찰 시스템은 시간이 지나면서 형성되는 durable pattern입니다.** 순간적인 상태 변화(HP, 에너지)를 쌓으면 의미 없는 노이즈만 생성됩니다. 의미 있는 기억은 "어떤 선택을 했고, 어떤 결과가 나왔으며, 다음에 참고할 만한가"에 관한 것입니다.

> 이 README도 AI 에이전트가 Harry의 지시에 따라 작성하고 수정 중입니다.

## 현재 상황: 기억의 질 개선 완료, 인프라 전환, 모니터링 중

가장 큰 고민이었던 **"무엇을 기억해야 하는가"**에 대한 1차적 해결을 마쳤습니다. 처음에는 AI가 매 커맨드마다 retain하여 500개가 넘는 memory unit이 쌓였는데, 대부분이 "에너지 2→1" 같은 상태 스냅샷이었습니다.

### 적용한 개선 사항

1. **Retain 타이밍 제한**: 매 커맨드 ❌, 턴 종료(END)만 ✅
2. **Retain 내용 템플릿**: Situation / Decision / Outcome / Lesson 구조 제시
3. **Hindsight Bank Mission 설정**: fact extraction이 전략/패턴/교훈을 추출하도록 유도
4. **Context field 강화**: raw state snapshot을 무시하도록 지시

### 인프라 전환: Python SDK + JSONL 로깅 + 새 뱅크

개선된 retain 품질을 깨끗한 공간에 쌓기 위해 **인프라를 전면 교체**했습니다:

- **`cli.py` + Python SDK**: 기존에 subprocess로 `hindsight` CLI를 호출하던 방식을 Hindsight Python SDK로 직접 호출하도록 변경했습니다. 타입 제어와 API 파라미터 활용이 훨씬 개선되었습니다.
- **`sts-v2` 뱅크**: 레거시 `sts` 뱅크(상태 스냅샷 500개 이상)는 보존하고, 2026-04-24 이후의 고품질 메모리 101개만 `sts-v2`로 이전했습니다. 현재 AI는 `sts-v2`를 사용합니다.
- **`retain_async=True`**: Python SDK `retain()`의 기본값이 `retain_async=False`여서 서버가 LLM fact extraction + embedding + DB insert를 모두 완료할 때까지 대기해야 했습니다. 이로 인해 60초 이상 소요되어 타임아웃이 발생했습니다. `retain_batch(retain_async=True)`로 변경한 후 즉시 반환 + 백그라운드 worker 처리로 타임아웃이 완전히 해소되었습니다.
- **JSON Lines 로깅**: `game.log`와 `ai.log`를 `game.jsonl`/`ai.jsonl`로 전환했습니다. 모든 이벤트를 구조화된 JSON으로 기록하여 `jq`로 필터링할 수 있습니다. 예: `jq 'select(.event == "retain") | .op_id'`
- **reasoning.jsonl 로깅**: LLM 호출마다 `{recall_result, reasoning_content}` 쌍을 JSONL로 기록합니다. recall 정보가 reasoning에 어떤 영향을 미치는지 분석할 수 있습니다.

### 발견한 버그

**Hindsight CLI/DB 스키마 불일치**: Hindsight 소스코드를 직접 분석한 결과, CLI의 `recall` 기본값이 `[world, experience, opinion]`인데, DB 마이그레이션(2026-04-02)에서 `opinion`은 이미 제거되고 `observation`이 추가되어 있었습니다. 결과적으로 고품질 기억이 consolidate되어 `observation`으로 생성되었음에도 `recall`로 검색되지 않는 치명적인 불일치였습니다. `cli.py`에서 SDK 레벨로 `types=["world", "experience", "observation"]`를 명시하여 해결했습니다.

### 결과: 개선 확인

**이전**: "에너지 2→1, Chosen HP 47→41" ❌
**현재**: "Against the Act 2 bandit encounter, Electro + Lightning orb passives were extremely effective. Red Mask is an excellent relic pickup since it applies Weak to all enemies at combat start, synergizing perfectly with Electro's AoE lightning." ✅

AI가 템플릿을 잘 준수하고, 시너지 분석과 빌드 방향을 포함하는 retain을 생성하고 있습니다.

### 모니터링 중인 사항

- **END 후 retain 누락**: ~~AI가 System prompt를 무시하고 retain을 하지 않는 경우 약 30%~~ **실제 누락 0건** — 이전 분석에서는 "END 후 다음 커맨드까지 retain이 없음"을 누락으로 판단했으나, 그 사이에 전투가 계속된 경우(다음 턴 PLAY/END/WAIT)도 포함되어 있었습니다. 전투 종료 후에는 모두 retain이 존재합니다.
- **Recall 지연**: 약 26초 (embedding 5초 + reranking 21초). Hindsight worker가 OpenClaw bank와 리소스 경쟁을 하는 것으로 추정됩니다. 기능적 문제는 없으나 전체 턴 시간이 증가하고 있습니다.

## 아키텍처 개요

```
AI (packages/ai) → Game CLI (packages/game) → Proxy (packages/proxy)
                                                       ↓ WebSocket
                                                 Bridge (packages/bridge)
                                                       ↓ stdin/stdout
                                            CommunicationMod (Java mod)
                                                       ↓
                                              Slay the Spire
```

AI는 OpenAI 호환 API(deepseek-v4-pro-precision via crof.ai)를 사용하며, tool-calling 방식으로 게임을 제어합니다. 장기기억은 Hindsight 뱅크에 저장됩니다.

자세한 기술 문서는 [AGENTS.md](AGENTS.md)를 참고하세요.

## 실행 방법

```sh
# 1. 의존성 설치
uv sync --all-packages --locked
git submodule update --init --recursive

# 2. CommunicationMod 빌드 (external/CommunicationMod에서 mvn package)
# 3. config.properties 설정 (절대 경로로 bridge 명령 지정)

# 4. 환경변수
export CROF_API_KEY=...

# 5. 실행 (별도 터미널)
uv run proxy   # 프록시 서버
uv run ai      # AI 에이전트
```

## 로드맵

- [x] 기본 AI 루프 구축
- [x] Hindsight 통합 (retain/recall)
- [x] Retain 전략 재설계 (빈도/내용 개선)
- [x] Hindsight CLI/DB mismatch 해결 (observation 타입 누락)
- [x] Python SDK 전환 (`cli.py`)
- [x] `sts-v2` 뱅크 생성 및 고품질 메모리 마이그레이션
- [x] Retain 타임아웃 해결 (`retain_async=True`)
- [x] LLM 전환: kimi-k2.6(OpenCode) → deepseek-v4-flash:cloud(Ollama Cloud) → deepseek-v4-pro-precision(crof.ai)
- [x] JSONL 로깅 전환 (ai.jsonl, game.jsonl)
- [x] LLM 메시지 덤프 (llm_dump/, 최근 10개)
- [x] LLM 응답 시간 측정 (duration_ms)
- [x] Recall 쿼리 개선 (class + screen + monsters)
- [x] ~~END 후 retain 누락 문제 분석~~ — **실제 누락 0건** 확인
- [x] reasoning.jsonl 로깅 (recall↔reasoning 쌍 분석 인프라)
- [x] `last_auto_query` 버그 수정
- [~] 효과 측정: 새로운 기억의 질 확인 (진행 중)
- [ ] Tags 도입 (class, topic, enemy 태깅)
- [ ] Mental model 생성 (직업별 빌드 가이드 등)
- [ ] Reflect 활용 (단순 recall → 전략 조언)
- [ ] **심장 클리어**

---

> 이 프로젝트는 단순히 게임을 플레이하는 AI를 만드는 것을 넘어, **"AI가 경험으로부터 학습하는 방법"**을 탐구하는 실험입니다. 그 과정에서 AI 에이전트와의 협업 자체도 배워가고 있습니다.
