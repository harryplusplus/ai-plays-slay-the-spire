# Slay the Spire Mod API 사용 가이드

## 목차

- 개요
- 확인한 환경과 실제 호출 결과
- 엔드포인트
- 응답 모델
- 권장 제어 흐름
- 명령 사용 규칙
- `curl` 예시
- Python 예시
- `/events` 활용법
- 주의사항

## 개요

이 API는 Slay the Spire의 CommunicationMod를 HTTP로 감싼 로컬 브리지다.
`http://localhost:8000`에 FastAPI 서버가 떠 있고, 실제 게임 제어는 `POST /execute`로 명령 문자열을 보내는 방식으로 이뤄진다.

핵심 포인트는 다음과 같다.

- HTTP 계층은 명령을 자체 해석하지 않고 거의 그대로 CommunicationMod에 전달한다.
- 대신 `--command-id=<id>`를 자동으로 붙여 응답과 요청을 매칭한다.
- 최근 명령과 메시지는 `/events`에서 조회할 수 있다.
- 실제로 보낼 수 있는 다음 명령은 응답의 `available_commands`를 기준으로 판단해야 한다.

## 확인한 환경과 실제 호출 결과

이 문서는 `2026-03-25`에 아래 조건에서 실제 호출을 확인하고 작성했다.

- OpenAPI 문서: `http://localhost:8000/openapi.json`
- 브리지 엔드포인트: `http://localhost:8000`
- 실제 확인한 명령:
- `STATE`
- `START DEFECT 0`
- `CHOOSE 0`
- 잘못된 명령 예시로 `PLAY 1`

실제로 확인한 상태 변화는 다음과 같았다.

- 메인 메뉴에서 `STATE` 호출 시 `available_commands`는 `["start","state"]`, `in_game`은 `false`였다.
- `START DEFECT 0` 호출 시 새 디펙트 런이 시작됐고 `in_game`이 `true`로 바뀌었다.
- 같은 응답에서 `game_state.class`는 `"DEFECT"`, `screen_type`은 `"EVENT"`, `screen_state.event_name`은 `"Neow"`, `choice_list`는 `["talk"]`였다.
- 이어서 `CHOOSE 0` 호출 시 Neow 보상 선택지 4개가 내려왔다.
- 이벤트 화면에서 `PLAY 1`을 보내면 `error` 필드에 잘못된 명령이라는 메시지가 내려왔다.

## 엔드포인트

### `POST /execute`

명령 하나를 실행하고, 그 명령에 대응하는 다음 안정 상태 메시지를 기다렸다가 반환한다.

요청 본문은 다음 형태다.

```json
{
  "command": "STATE"
}
```

응답은 `Message` 모델이다.

### `GET /events?limit=<n>`

최근 이벤트를 조회한다.

- 이벤트 종류는 주로 `command` 또는 `message`다.
- `message`의 `data`는 JSON 객체가 아니라 JSON 문자열이다.
- 최근 `n`개를 고른 뒤, 결과는 오래된 것부터 정렬돼 반환된다.

## 응답 모델

`POST /execute` 응답의 핵심 필드는 다음과 같다.

- `command_id`: 브리지가 자동으로 부여한 요청 식별자
- `ready_for_command`: 다음 명령을 받아도 되는 상태인지 여부
- `error`: 실행 실패 시 오류 문자열
- `available_commands`: 지금 화면에서 가능한 명령 목록
- `in_game`: 현재 게임 안인지 여부
- `game_state`: 현재 게임 상태 객체

실무적으로는 아래 순서로 읽으면 된다.

1. `error`가 있는지 먼저 본다.
2. `ready_for_command`가 `true`인지 확인한다.
3. `available_commands`에 원하는 명령이 실제로 열려 있는지 확인한다.
4. `game_state`에서 현재 화면과 세부 선택지를 읽는다.

## 권장 제어 흐름

자동화 루프는 아래처럼 구성하면 가장 덜 위험하다.

1. 먼저 `STATE`를 호출하거나 직전 응답을 재사용한다.
2. `ready_for_command`가 `true`인지 확인한다.
3. `available_commands`에 없는 명령은 보내지 않는다.
4. `game_state.screen_type`, `game_state.screen_state`, `game_state.choice_list`, `game_state.combat_state`를 읽고 다음 행동을 결정한다.
5. 가능한 한 `CHOOSE`, `PLAY`, `END`, `POTION`, `PROCEED`, `RETURN` 같은 의미 기반 명령을 쓴다.
6. 정말 필요할 때만 `KEY`, `CLICK`으로 내려간다.

이 브리지는 요청 하나를 보낸 뒤 응답이 올 때까지 기다리는 RPC 스타일에 가깝다.
브리지 구현상 약 30초 안에 응답이 없으면 타임아웃 오류를 돌려준다.

## 명령 사용 규칙

아래 명령들은 CommunicationMod 규칙을 그대로 따른다.
HTTP API는 이 문자열을 `command`에 실어 보내면 된다.

### `STATE`

현재 상태를 즉시 다시 요청한다.
가장 안전한 시작점이다.

### `START PlayerClass [AscensionLevel] [Seed]`

새 게임을 시작한다.

- 메인 메뉴에서만 가능하다.
- 실제로 `START DEFECT 0` 호출이 성공하는 것을 확인했다.
- 시드는 생략 가능하다.
- 클래스와 명령 이름은 대소문자를 가리지 않는다.

### `CHOOSE ChoiceIndex|ChoiceName`

현재 화면의 선택지를 고른다.

- 실제로 `CHOOSE 0`이 Neow 이벤트에서 동작했다.
- 가능하면 `game_state.screen_state.options[].choice_index`를 그대로 쓰는 편이 안전하다.
- 이름으로도 고를 수 있지만, 화면 문구가 길거나 유사할 수 있으므로 인덱스가 더 안전하다.

### `PLAY CardIndex [TargetIndex]`

전투 중 손패의 카드를 사용한다.

- `CardIndex`는 1부터 시작한다.
- `TargetIndex`는 몬스터 배열 기준 0부터 시작한다.
- 현재 화면에서 `available_commands`에 `play`가 없는데 `PLAY`를 보내면 오류가 난다.

### `END`

전투에서 턴을 종료한다.

### `POTION Use|Discard PotionSlot [TargetIndex]`

포션을 사용하거나 버린다.

- 타깃이 필요한 포션은 `TargetIndex`를 함께 보낸다.
- 슬롯 번호 체계는 이 HTTP 스펙에 별도로 설명돼 있지 않으므로 실제 사용 전 작은 범위에서 검증하는 편이 안전하다.

### `PROCEED`

오른쪽 진행 버튼을 누른다.
`CONFIRM`과 같은 의미다.

### `RETURN`

왼쪽 복귀 버튼을 누른다.
`SKIP`, `CANCEL`, `LEAVE`와 같은 의미다.

### `KEY Keyname [Timeout]`

지정한 키를 누른다.

- 메뉴 열기, 카드 집기 등 의미 기반 명령이 없을 때만 사용한다.
- 가능한 키 이름은 CommunicationMod README의 키 목록을 따른다.

### `CLICK Left|Right X Y`

지정 좌표를 마우스로 클릭한다.

- 좌표 기준은 항상 `(0,0)`이 좌상단, `(1920,1080)`이 우하단이다.
- 게임 해상도와 무관하게 이 좌표계를 쓴다.

### `WAIT Timeout`

지정 프레임 수만큼 기다리거나 상태 변화가 감지될 때까지 대기한 뒤 현재 상태를 반환한다.

## `curl` 예시

### 1. 현재 상태 확인

```sh
curl -sS -X POST http://localhost:8000/execute \
  -H 'content-type: application/json' \
  -d '{"command":"STATE"}'
```

메인 메뉴에서 실제로 확인한 핵심 응답은 아래와 비슷했다.

```json
{
  "command_id": "11",
  "ready_for_command": true,
  "error": null,
  "available_commands": ["start", "state"],
  "in_game": false,
  "game_state": null
}
```

### 2. 디펙트 런 시작

```sh
curl -sS -X POST http://localhost:8000/execute \
  -H 'content-type: application/json' \
  -d '{"command":"START DEFECT 0"}'
```

실제로 확인한 핵심 응답 포인트는 아래와 같았다.

```json
{
  "ready_for_command": true,
  "available_commands": ["choose", "key", "click", "wait", "state"],
  "in_game": true,
  "game_state": {
    "class": "DEFECT",
    "screen_type": "EVENT",
    "screen_state": {
      "event_name": "Neow"
    },
    "choice_list": ["talk"]
  }
}
```

### 3. Neow 첫 대화 진행

```sh
curl -sS -X POST http://localhost:8000/execute \
  -H 'content-type: application/json' \
  -d '{"command":"CHOOSE 0"}'
```

실제로 이 호출 뒤 Neow 보상 선택지 4개가 반환됐다.

- `Obtain a random rare Card`
- `Max HP +7`
- `Lose all Gold Remove 2 Cards`
- `Lose your starting Relic Obtain a random boss Relic`

### 4. 허용되지 않은 명령 오류 확인

이벤트 화면에서는 `play`가 열려 있지 않으므로 아래 호출은 실패한다.

```sh
curl -sS -X POST http://localhost:8000/execute \
  -H 'content-type: application/json' \
  -d '{"command":"PLAY 1"}'
```

실제로 확인한 응답은 아래와 같았다.

```json
{
  "command_id": "14",
  "ready_for_command": true,
  "error": "Invalid command: play. Possible commands: [choose, key, click, wait, state]",
  "available_commands": null,
  "in_game": null,
  "game_state": null
}
```

## Python 예시

표준 라이브러리만으로도 충분히 호출할 수 있다.

```python
import json
from urllib import request


def execute(command: str) -> dict:
    payload = json.dumps({"command": command}).encode()
    req = request.Request(
        "http://localhost:8000/execute",
        data=payload,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with request.urlopen(req) as response:
        return json.loads(response.read().decode())


state = execute("STATE")
if state["ready_for_command"] and "start" in (state.get("available_commands") or []):
    result = execute("START DEFECT 0")
    print(result["game_state"]["screen_type"])
```

## `/events` 활용법

최근 명령과 응답을 짧게 확인하려면 `/events`가 편하다.

```sh
curl -sS 'http://localhost:8000/events?limit=5'
```

이 응답에서 확인할 점은 다음과 같다.

- `kind="command"`면 브리지가 실제로 보낸 명령이다.
- `kind="message"`면 게임이 돌려준 원문 메시지다.
- `command` 이벤트의 `data`에는 브리지가 붙인 `--command-id=<id>`가 포함된다.
- `message` 이벤트의 `data`는 문자열이므로 필요하면 JSON으로 다시 파싱해야 한다.

디버깅할 때는 아래 흐름으로 보면 편하다.

1. 마지막 `command` 이벤트를 본다.
2. 바로 뒤 `message` 이벤트의 `command_id`가 같은지 확인한다.
3. 오류면 `error`를 읽고, 정상이면 `available_commands`와 `game_state`를 읽는다.

## 주의사항

- `available_commands`를 무시하고 명령을 보내지 않는다.
- `STATE`는 가장 안전한 동기화 명령이므로 상태가 애매하면 다시 호출한다.
- `PLAY`는 카드 인덱스가 1부터 시작한다.
- `CHOOSE`는 실제 화면의 `choice_index`를 쓰는 편이 가장 안전하다.
- `KEY`와 `CLICK`은 해상도나 입력 포커스에 민감하므로 최후의 수단으로 남긴다.
- CommunicationMod의 알려진 제약은 원본 README를 따른다. 예를 들어 일부 이벤트 상태는 완전하지 않을 수 있고, 포션 인벤토리가 꽉 찬 경우 특정 행동에 피드백이 없을 수 있다.
- HTTP API 사용자는 `ready` 신호를 직접 보낼 필요가 없다. 브리지 시작 시 내부적으로 처리된다.
- `--command-id=...`도 직접 붙이지 않는다. `POST /execute`가 자동으로 처리한다.
