# Workspace Memory

## STS Helpers
- `./scripts/sts-state-latest.sh`
  - 최근 `message` 이벤트에서 최신 JSON 상태를 꺼냅니다.
  - 기본 조회 범위는 최근 `20`개 이벤트이고, 필요하면 첫 번째 인자로 더 크게 줍니다.
  - 현재 작업 디렉터리에서 그대로 실행합니다. 실행 전에 디렉터리를 바꾸지 않습니다.
- `./scripts/sts-combat-summary.sh`
  - 최신 상태에서 전투 요약만 짧게 뽑습니다.
  - 손패, 에너지, 적 의도, 오브, 파워, discard의 0코스트 카드가 포함됩니다.
  - 현재 작업 디렉터리에서 그대로 실행합니다. 실행 전에 디렉터리를 바꾸지 않습니다.

## Usage Notes
- 두 스크립트 모두 미래 메시지를 기다리지 않고, 이미 기록된 이벤트만 읽습니다.
- 최근 이벤트 범위 안에 `message`가 없으면 실패하므로, 그때는 `50` 같은 더 큰 limit로 다시 실행합니다.

## CommunicationMod Update Checklist
- [x] 최신 CommunicationMod로 게임을 다시 켠 뒤 `uv run sts events --limit 1` 에서 `message` 이벤트가 정상적으로 들어오는지 확인합니다.
- [x] `./scripts/sts-state-latest.sh` 가 그대로 동작하는지 확인합니다.
- [x] `./scripts/sts-combat-summary.sh` 가 그대로 동작하는지 확인합니다.
- [x] 최신 mod에서 상태 JSON 구조가 바뀐 필드를 확인합니다.
- [x] `play`/`choose` 이후 이벤트 흐름이나 메시지 타이밍을 확인합니다.
- [ ] 카드 이름 기반 보조 래퍼가 여전히 필요한지 다시 판단합니다.

### Confirmed Payload Changes
- `game_state.keys` 필드가 추가되어 루비/에메랄드/사파이어 키 상태를 바로 확인할 수 있습니다.
- 비전투 화면에서는 `combat_state` 를 가정하면 안 됩니다.
- 비전투 선택 화면에서는 `choice_list` 와 `screen_state.options` 가 함께 내려옵니다.
- 일부 선택 화면에서는 `available_commands` 에 `confirm` 과 `cancel` 이 직접 노출됩니다.

### Confirmed Flow Notes
- `command_recorded` 뒤에 `message` 가 이어지는 기본 흐름은 유지됩니다.
- 상점 `purge` 같은 그리드 선택은 카드 선택 후 `confirm` 으로 확정하는 흐름이 보입니다.
