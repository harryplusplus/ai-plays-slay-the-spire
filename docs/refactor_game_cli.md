# game CLI 리팩터링 계획

> **SOT (Single Source of Truth)** — 이 문서가 유일한 설계 기준.
> 기능 변경이 아니다. 구조만 바꾼다. 각 명령어의 동작과 인터페이스는 그대로 유지.

## 동기

- `cli.py`가 one-file 앱이라 명령어가 늘수록 유지보수 어려움
- 각 명령어를 독립적인 파일/모듈로 분리하여 관찰가능성과 테스트 용이성 확보
- `ai` 패키지에 흩어진 기능(스크린샷 등)을 `game` CLI로 흡수하여 단일 게이트웨이로 만듦
- 로깅에 추가 문맥(`--tag`)을 붙일 수 있는 기반 마련

## 원칙

1. **기능 변경 금지** — 명령어 이름, 인자, 출력 포맷은 그대로
2. **공통 코드는 `cli.py`와 같은 계층** — `log.py`처럼 `game/` 아래에 직접 둠 (commands/ 안에 넣지 않음)
3. **각 명령어는 `game/commands/<name>.py`** — 파일 하나에 명령어 하나
4. **`cli.py`는 Typer app 생성과 명령어 등록만** — 비즈니스 로직 없음

## 최종 디렉토리 구조

```
packages/game/src/game/
├── __init__.py
├── cli.py                  # Typer app, 명령어 등록 (dispatcher)
├── log.py                  # JsonlFormatter, init_logger()  ← 기존 cli.py에서 분리
├── commands/
│   ├── __init__.py
│   ├── command.py          # game command <cmd>
│   ├── deck.py             # game deck
│   ├── relics.py           # game relics
│   ├── potions.py          # game potions
│   ├── map.py              # game map
│   ├── recall.py           # game recall <query>
│   ├── retain.py           # game retain <content>
│   └── screenshot.py       # game screenshot [--output-dir] [--max-files]
└── utils/
    ├── __init__.py
    ├── proxy.py            # send_command() — httpx POST to proxy
    └── hindsight.py        # Hindsight client 초기화 (BANK_ID, RETAIN_CONTEXT 등)
```

## 명령어별 책임

| 명령어 | 파일 | 현재 상태 | 비고 |
|--------|------|-----------|------|
| `command` | `commands/command.py` | cli.py에 있음 | `send_command()` 호출, `_check_start_class()` 포함 |
| `deck` | `commands/deck.py` | cli.py에 있음 | `state` 명령 결과에서 deck 추출 |
| `relics` | `commands/relics.py` | cli.py에 있음 | `state` 명령 결과에서 relics 추출 |
| `potions` | `commands/potions.py` | cli.py에 있음 | `state` 명령 결과에서 potions 추출 |
| `map` | `commands/map.py` | cli.py에 있음 | `state` 명령 결과에서 map 추출 |
| `recall` | `commands/recall.py` | cli.py에 있음 | Hindsight recall |
| `retain` | `commands/retain.py` | cli.py에 있음 | Hindsight retain |
| `screenshot` | `commands/screenshot.py` | **신규** | `window.py`에서 이관, CoreGraphics 캡처 + 파일 저장 + 로테이션 |

## 공통 유틸리티

### `utils/proxy.py`

```python
def send_command(cmd: str) -> dict[str, Any]:
    """proxy에 명령 전송. httpx POST."""
```

현재 `cli.py`의 `send_command()`를 그대로 이동.

### `utils/hindsight.py`

```python
BANK_ID = "sts-v2"
RETAIN_CONTEXT = "..."
HINDSIGHT_URL = "http://localhost:8888"

def create_client() -> Hindsight: ...
```

현재 `cli.py`의 상수와 Hindsight client 생성을 이동.

## `cli.py` (after)

```python
"""game CLI — Typer app entry point."""

from .commands import command, deck, relics, potions, map, recall, retain, screenshot
from .log import init_logger

app = typer.Typer(no_args_is_help=True, add_completion=False)
app.command()(command.command)
app.command()(deck.deck)
app.command()(relics.relics)
app.command()(potions.potions)
app.command(map.name)(map.map_cmd)
app.command()(recall.recall)
app.command()(retain.retain)
app.command()(screenshot.screenshot)

def main() -> None:
    init_logger()
    app()
```

## `commands/screenshot.py` (신규)

`packages/ai/src/ai/window.py`의 CoreGraphics 캡처 로직을 이관.
Pillow 의존성은 `game` 패키지로 이동.

```python
@app.command()
def screenshot(
    output_dir: str = str(Path.home() / ".sts" / "screenshots"),
    max_files: int = 1000,
) -> None:
    """Capture Slay the Spire window and save as JPEG."""
    ...
```

출력 포맷 (stdout):
```json
{"path": "/Users/harry/.sts/screenshots/20260507_080000_123456.jpg", "size": 45231}
```

## AI 쪽 변경 (Phase 2)

- `packages/ai/src/ai/window.py` 제거
- `main.py`의 `capture_screenshot()` 호출을 `game_cli("screenshot")`으로 대체
- 반환된 JSON에서 `path`를 읽어 파일을 b64로 변환
- `Pillow` 의존성 `ai/pyproject.toml`에서 제거 (선택)

## 로깅 개선 (Phase 3, 선택)

각 명령어에 `--tag` 공통 옵션 추가:
```bash
game screenshot --tag "act=3" --tag "boss=awakened"
```

로그에 `tags` 필드로 기록.

## 단계

### Phase 1 — 구조 분리 (동작 유지)
1. `log.py` 분리
2. `utils/proxy.py` 분리
3. `utils/hindsight.py` 분리
4. 각 `commands/*.py` 생성 + 기존 cli.py에서 코드 이동
5. `cli.py`를 dispatcher로 축소
6. `commands/screenshot.py` 구현 (window.py에서 이관)
7. `game/pyproject.toml`에 `Pillow` 추가

### Phase 2 — AI 쪽 정리
1. `window.py` 제거
2. `main.py`에서 `game_cli("screenshot")` 호출로 대체
3. `ai/pyproject.toml`에서 `Pillow` 제거 (선택)

### Phase 3 — 로깅 개선 (선택)
1. `--tag` 공통 옵션 추가
2. 각 명령어 로그에 tags 포함
