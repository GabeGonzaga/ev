"""Where macros live: one JSON file, beside the journal.

Not in the database. A macro is something a person writes, reads and shares,
and a file can be opened in an editor, kept in a dotfiles repository, and
deleted without a query.
"""

from __future__ import annotations

import json
from pathlib import Path

from ev.domain.macro import Macro

MACROS_FILE = "macros.json"


def macros_path(state_dir: Path) -> Path:
    return state_dir / MACROS_FILE


def load_macros(path: Path) -> dict[str, Macro]:
    if not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path}: expected a list of macros")

    macros = [Macro.model_validate(entry) for entry in payload]
    by_name: dict[str, Macro] = {}
    for macro in macros:
        # Two macros with one name is a question nobody can answer at run
        # time, so it is answered here.
        if macro.name.casefold() in by_name:
            raise ValueError(f"{path}: two macros are called {macro.name!r}")
        by_name[macro.name.casefold()] = macro
    return by_name


def save_macros(path: Path, macros: list[Macro]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [json.loads(macro.model_dump_json()) for macro in macros]
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
