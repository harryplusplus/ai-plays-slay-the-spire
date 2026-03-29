import json  # noqa: INP001
from pathlib import Path

output = {}


if not Path("CLEAR.md").exists():
    output["decision"] = "block"
    output["reason"] = (
        "심장을 격파했으면 `CLEAR.md` 파일을 생성하고, 그렇지 않다면 심장을 격파해."
    )


print(json.dumps(output), flush=True)  # noqa: T201
