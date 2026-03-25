# Enhancement Requests

## 1. Hologram / Hologram+ GRID 선택 안정화

- 현상: `Hologram` 또는 `Hologram+` 사용 시 `GRID` 선택 화면이 열리는데, 자동화 입장에서는 어떤 카드를 어떤 기준으로 선택해야 하는지 매 턴 안정적으로 식별하기가 어렵습니다.
- 요청: `GRID` 화면에서 각 카드에 대해 `choice_index`와 `uuid`를 함께 노출하고, `CHOOSE <choice_index>` 또는 `CHOOSE <uuid>` 같은 안정적인 선택 방식을 공식적으로 지원해주면 좋겠습니다.
- 기대효과: 카드 회수 자동화 실수가 줄고, `Hologram` 계열을 포함한 각종 선택 로직의 신뢰도가 크게 올라갑니다.

### 현재 응답 예시

최근 이벤트 로그에서 실제로 확인한 `GRID` 응답은 아래와 같은 형태였습니다.

```json
{
  "available_commands": ["choose", "key", "click", "wait", "state"],
  "game_state": {
    "screen_type": "GRID",
    "screen_state": {
      "cards": [
        {
          "name": "Ball Lightning",
          "uuid": "2c1abe9c-c363-441c-a5ce-27fae0fc72f3",
          "cost": 1
        },
        {
          "name": "Ball Lightning",
          "uuid": "2ad8a18c-0137-4413-a91e-a8e7b154fa97",
          "cost": 1
        },
        {
          "name": "Burn",
          "uuid": "2d0583f9-2d8f-4c5e-a168-8e76a900dce9",
          "cost": -2
        },
        {
          "name": "Burn",
          "uuid": "dfc46fd6-a708-4cb3-956f-3993779f769c",
          "cost": -2
        }
      ],
      "selected_cards": [],
      "num_cards": 1
    },
    "choice_list": [
      "ball lightning",
      "ball lightning",
      "burn",
      "burn"
    ]
  }
}
```

- 문제점 1: `screen_state.cards[]`에는 `uuid`가 있지만, 실제 선택에 바로 쓸 수 있는 `choice_index`가 없습니다.
- 문제점 2: `choice_list`는 이름만 내려오므로 `Ball Lightning`, `Burn`처럼 중복 카드가 있으면 이름 기반 `CHOOSE`가 모호합니다.
- 문제점 3: 자동화 쪽에서는 결국 "카드 배열 순서와 `choice_list` 순서가 같을 것이다"라는 추론에 의존해야 해서 안정성이 떨어집니다.

### 원하는 응답 예시

아래처럼 각 카드에 선택용 식별자를 직접 붙여주면 가장 다루기 쉬워집니다.

```json
{
  "available_commands": ["choose", "key", "click", "wait", "state"],
  "game_state": {
    "screen_type": "GRID",
    "screen_state": {
      "cards": [
        {
          "choice_index": 0,
          "name": "Ball Lightning",
          "uuid": "2c1abe9c-c363-441c-a5ce-27fae0fc72f3",
          "cost": 1
        },
        {
          "choice_index": 1,
          "name": "Ball Lightning",
          "uuid": "2ad8a18c-0137-4413-a91e-a8e7b154fa97",
          "cost": 1
        },
        {
          "choice_index": 2,
          "name": "Burn",
          "uuid": "2d0583f9-2d8f-4c5e-a168-8e76a900dce9",
          "cost": -2
        },
        {
          "choice_index": 3,
          "name": "Burn",
          "uuid": "dfc46fd6-a708-4cb3-956f-3993779f769c",
          "cost": -2
        }
      ],
      "selected_cards": [],
      "num_cards": 1
    }
  }
}
```

- 이 형태면 `CHOOSE 1`처럼 인덱스로 안정적으로 고를 수 있습니다.
- 더 좋게는 `CHOOSE 2ad8a18c-0137-4413-a91e-a8e7b154fa97`처럼 `uuid`를 직접 받게 하면 카드명 중복과 배열 순서 의존을 동시에 없앨 수 있습니다.
- 기존 `EVENT` 화면의 `screen_state.options[].choice_index` 패턴과도 유사해서 클라이언트 쪽 구현 일관성도 좋아집니다.

## 2. Compact Combat Summary 추가

- 현상: 현재 `STATE` 응답은 정보가 매우 풍부하지만 길이가 길어서, 매 턴 핵심 전투 정보만 빠르게 읽고 판단하기가 어렵습니다.
- 요청: 손패, 에너지, 블록, 오브, 적 체력/블록/의도, 포션, 현재 화면 상태만 짧게 모아 보여주는 `compact combat summary`를 별도 필드나 명령으로 제공해주면 좋겠습니다.
- 기대효과: 매 턴 의사결정 속도와 정확도가 올라가고, 카드 인덱스 재정렬이나 상태 변화도 더 빠르게 검증할 수 있습니다.
