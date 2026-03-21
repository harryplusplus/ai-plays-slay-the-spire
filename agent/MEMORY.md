# Workspace Memory

## STS Helpers
- `./scripts/sts-state-latest.sh`
  - 최근 `message` 이벤트에서 최신 JSON 상태를 꺼냅니다.
  - 기본 조회 범위는 최근 `20`개 이벤트이고, 필요하면 첫 번째 인자로 더 크게 줍니다.
  - `agent` 작업 디렉터리에서 실행하는 것을 기준으로 둡니다.
- `./scripts/sts-combat-summary.sh`
  - 최신 상태에서 전투 요약만 짧게 뽑습니다.
  - 손패, 에너지, 적 의도, 오브, 파워, discard의 0코스트 카드가 포함됩니다.
  - `agent` 작업 디렉터리에서 실행하는 것을 기준으로 둡니다.

## Usage Notes
- 두 스크립트 모두 미래 메시지를 기다리지 않고, 이미 기록된 이벤트만 읽습니다.
- 최근 이벤트 범위 안에 `message`가 없으면 실패하므로, 그때는 `50` 같은 더 큰 limit로 다시 실행합니다.

## CommunicationMod Update Checklist
- [ ] 최신 CommunicationMod로 게임을 다시 켠 뒤 `uv run sts events --limit 1` 에서 `message` 이벤트가 정상적으로 들어오는지 확인합니다.
- [ ] `./scripts/sts-state-latest.sh` 가 그대로 동작하는지 확인합니다.
- [ ] `./scripts/sts-combat-summary.sh` 가 그대로 동작하는지 확인합니다.
- [ ] 최신 mod에서 상태 JSON 구조가 바뀐 필드가 없는지 확인합니다.
- [ ] `play`/`choose` 이후 이벤트 흐름이나 메시지 타이밍이 이전과 달라졌는지 확인합니다.
- [ ] 카드 이름 기반 보조 래퍼가 여전히 필요한지 다시 판단합니다.
