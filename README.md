# AI Plays Slay the Spire

> 이 문서는 **kimi-k2.6**이 Harry의 지시에 따라 한국어로 작성하고 유지보수하는 문서입니다. 모델의 한국어 출력 과정에서 낮은 확률로 글자가 잘못 조합되는 버그가 있어, 의도는 올바른 한국어이나 출력에 가끔 사소한 오타가 포함될 수 있습니다. 이 점 양해 부탁드립니다.

이 저장소는 **Harry**와 AI 코딩 에이전트가 함께 만드는 **Slay the Spire 자동 플레이 봇**이다. 궁극적인 목표는 승천 0, 디펙트로 **심장(Heart) 클리어**를 하는 것이지만, 그 과정에서 배우는 것이 더 중요하다.

## 이 프로젝트가 특별한 이유

대부분의 게임 플레이 봇은 "지금 이 판을 이기는 것"만 목표로 한다. 이 프로젝트는 다르다. **Hindsight 장기기억 시스템을 통해 각 게임에서 얻은 전략적 교훈을 축적하고, 다음 런에서 회상하여 활용한다.** 단순히 프롬프트 컨텍스트에 의존하는 것이 아니라, 외부 메모리 뱅크에 지속적으로 기억을 쌓고 검색하는 구조다.

단순히 "게임을 하는 에이전트"를 넘어, **"과거 경험을 기억하고 활용하는 장기기억 LLM 에이전트"**를 만들고자 한다.

## 우리의 협업 방식

이 프로젝트는 Harry 혼자 코드를 쓰지 않는다. **AI 코딩 에이전트(Pi)와 협업**하며 개발한다.

**우리의 역할 분담:**

| Harry | AI 에이전트 |
|-------|------------|
| 전략적 제안 및 방향 설정 | 자료 조사 및 기술 문서 탐색 |
| 피드백과 질문 | 코드 작성 및 리팩토링 |
| 게임/기억 시스템의 크리티컬한 제어 결정 | AI 플레이어 세션 실행 및 모니터링 |
| 목표와 기대치 정의 | 구현 및 테스트 |

이 과정에서 우리가 발견한 중요한 교훈:

- **AI는 섣불리 "개선"하려 한다.** 충분한 정보 수집 없이 바로 코드를 고치려는 성향이 있어서, Harry는 "분석이 부족해", "정확히 파악하고" 같은 피드백을 계속 줘야 했다.
- **문서화는 생각의 지배 구조를 바꾼다.** AGENTS.md를 통해 프로젝트의 현재 상태, 문제, 가설, 시도한 것들을 기록하면서, 우리는 더 체계적으로 접근하게 되었다.
- **Hindsight의 관찰 시스템은 시간이 지나면서 형성되는 durable pattern이다.** 순간적인 상태 변화(HP, 에너지)를 쌓으면 의미없는 noise만 생긴다. 의미있는 기억은 "어떤 선택을 했고 어떤 결과가 나왔고 다음에 참고할만한가"에 대한 것이어야 한다.

> 이 리드미 역시 AI 에이전트가 Harry의 지시에 따라 작성하고 수정 중이다.

## 현재 상황: 기억의 질 개선 완료, 인프라 전환, 모니터링 중

가장 큰 고민이었던 **"무엇을 기억해야 하는가"**에 대한 1차적인 해결을 마쳤다. 처음에는 AI가 매 커맨드마다 retain해서 500개가 넘는 memory unit이 쌓였으나, 대부분이 "에너지 2→1" 같은 상태 스냅샷이었다.

### 우리가 한 개선

1. **Retain 타이밍 제한**: 매 커맨드 ❌, 턴 종료(END)만 ✅
2. **Retain 내용 템플릿**: Situation / Decision / Outcome / Lesson 구조 제시
3. **Hindsight Bank Mission 설정**: fact extraction이 전략/패턴/교훈을 추출하도록 유도
4. **Context field 강화**: raw state snapshot 무시하도록 지시

### 인프라 전환: Python SDK + 새 뱅크

개선된 retain 품질을 깨끗한 공간에 쌓기 위해 **인프라를 전면 교체**했다:

- **`cli_v2.py` + Python SDK**: 기존 subprocess로 `hindsight` CLI를 호출하던 방식에서, Hindsight Python SDK(`hindsight-client`)를 직접 사용하도록 전환. 더 정확한 타입 제어와 API 파라미터 활용이 가능해졌다.
- **`sts-v2` 뱅크**: 레거시 `sts` 뱅크(상태 스냅샷 500개+)를 버리지 않고 보존한 채, 2026-04-24 이후 고품질 메모리 101개만 `sts-v2`로 이전. 이제 AI는 `sts-v2`를 사용한다.
- **`retain_async=True`**: Python SDK의 `retain()`은 기본값이 `retain_async=False`로, 서버가 LLM fact extraction + embedding + DB insert를 모두 끝낼 때까지 HTTP 연결을 유지한다. 이게 60초를 넘어 타임아웃이 났었다. `retain_batch(retain_async=True)`로 바꿔서 즉시 반환 + 백그라운드 worker 처리로 변경하니 타임아웃이 완전히 사라졌다.

### 발견한 버그들

**Hindsight CLI/DB 스키마 불일치**: Hindsight 소스코드를 직접 읽어보니, CLI의 `recall` 기본값은 `[world, experience, opinion]`인데, DB 마이그레이션(2026-04-02)에서 `opinion`은 이미 제거되고 `observation`이 추가되어 있었다. 결과적으로 우리가 개선한 고품질 기억이 consolidate되어 `observation`으로 생성되었으나, `recall`로는 검색되지 않는 치명적 불일치가 있었다. 이것을 `cli.py`에서 `--fact-type`을 명시적으로 지정하는 것으로 우회했고, `cli_v2.py`에서는 SDK 레벨에서 `types=["world", "experience", "observation"]`를 명시했다.

### 결과: 개선 확인됨

**이전**: "에너지 2→1, Chosen HP 47→41" ❌
**지금**: "Against the Act 2 bandit encounter, Electro + Lightning orb passives were extremely effective. Red Mask is an excellent relic pickup since it applies Weak to all enemies at combat start, synergizing perfectly with Electro's AoE lightning." ✅

AI가 템플릿을 따륾고, 시너지 분석과 빌드 방향을 포함하는 retain을 생성하고 있다.

### 모니터링 중인 사항

- **END 후 retain 누락**: AI가 System prompt를 따르지 않고 END 후 retain을 호출하지 않는 경우가 ~30%. Tool call은 LLM의 선택이므로, code-level 강제 호출을 고려 중.
- **Recall 지연**: ~26초 (embedding 5s + reranking 21s). Hindsight worker가 OpenClaw bank와 리소스를 경쟁하는 것으로 추정. 기능적 문제는 없으나 전체 턴 시간 증가.

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

AI는 OpenAI 호환 API(kimi-k2.6 via OpenCode)를 사용하며, tool-calling 방식으로 게임을 제어한다. 장기기억은 Hindsight 뱅크(`sts`)에 저장된다.

자세한 기술 문서는 [AGENTS.md](AGENTS.md)에 기록되어 있다.

## 실행 방법

```sh
# 1. 의존성 설치
uv sync --all-packages --locked
git submodule update --init --recursive

# 2. CommunicationMod 빌드 (external/CommunicationMod에서 mvn package)
# 3. config.properties 설정 (절대 경로로 bridge 명령 지정)

# 4. 환경변수
export OPENCODE_API_KEY=...

# 5. 실행 (별도 터미널)
uv run proxy   # 프록시 서버
uv run ai      # AI 에이전트
```

## 로드맵

- [x] 기본 AI 루프 구축
- [x] Hindsight 통합 (retain/recall)
- [x] Retain 전략 재설계 (빈도/내용 개선)
- [x] Hindsight CLI/DB mismatch 해결 (observation 타입 누락)
- [x] Python SDK 전환 (`cli_v2.py`)
- [x] `sts-v2` 뱅크 생성 및 고품질 메모리 마이그레이션
- [x] Retain 타임아웃 해결 (`retain_async=True`)
- [~] 효과 측정: 새로운 기억의 질 확인 (진행 중 — 템플릿 준수 확인됨, async retain 안정성 관찰 중)
- [~] END 후 retain 누락 문제 분석 (AI 자발적 호출에 의존, code-level 강제 호출 검토)
- [ ] Mental model 생성 ("디펙트 빌드 가이드" 등)
- [ ] Tags/Entity labels 활용으로 검색 품질 향상
- [ ] Reflect 활용 (단순 recall → 전략 조언)
- [ ] **심장 클리어**

---

> 이 프로젝트는 단순히 게임을 플레이하는 AI를 만드는 것을 넘어, **"AI가 경험으로부터 학습하는 방법"**을 탐구하는 실험이기도 하다. 그 과정에서 AI 에이전트와의 협업 자체도 배워가고 있다.
