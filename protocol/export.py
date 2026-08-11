"""Write the JSON Schema that Rust and TypeScript will consume.

    make protocol          regenerate
    make protocol-check    fail if the committed artifact is stale

`generated/` is committed on purpose. It is the thing three languages agree on,
so it belongs in the diff of the commit that changes it -- not produced at
build time where only the machine that built it ever saw the change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from protocol.messages import PROTOCOL_VERSION, Envelope

GENERATED = Path(__file__).resolve().parent / "generated"
SCHEMA = GENERATED / "ev.schema.json"


def schema() -> dict[str, Any]:
    document = Envelope.model_json_schema(mode="serialization")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ev.local/protocol/ev.schema.json",
        "title": f"E.V. IPC protocol {PROTOCOL_VERSION}",
        "x-ev-protocol-version": PROTOCOL_VERSION,
        **document,
    }


def render() -> str:
    return json.dumps(schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write() -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    SCHEMA.write_text(render(), encoding="utf-8")
    print(f"wrote {SCHEMA}")


def check() -> int:
    if not SCHEMA.exists():
        print(f"{SCHEMA} is missing. Run: make protocol", file=sys.stderr)
        return 1

    if SCHEMA.read_text(encoding="utf-8") != render():
        print(
            f"{SCHEMA} is stale: protocol/messages.py has changed.\n"
            "Run: make protocol -- and commit the result, because Rust and "
            "TypeScript read that file, not the Python.",
            file=sys.stderr,
        )
        return 1

    print(f"{SCHEMA.name} matches protocol/messages.py")
    return 0


def main(argv: list[str]) -> int:
    if "--check" in argv:
        return check()
    write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
