"""Matching a spoken name against the names that actually exist.

`CLAUDE.md` states the rule for shortcuts -- "the name is resolved against the
real list of installed shortcuts, never passed through freely" -- and it holds
wherever a person says a name someone else typed. A playlist called
`Indie kid??` and a Notes folder called `Trabalho / 2026` are the same problem.

Pure text, no I/O, so it lives here and both capabilities use one
implementation rather than two that drift.
"""

from __future__ import annotations

import re

_NOISE = re.compile(r"[^\w]+", re.UNICODE)


def simplify(name: str) -> str:
    """What a name sounds like, with the punctuation nobody says removed.

    `{Jazzy}`, `Indie kid??` and `Main PlayList :D` are real playlist names.
    Nobody dictates the braces.
    """
    return _NOISE.sub("", name).casefold()


def closest(spoken: str, existing: list[str]) -> str | None:
    """The one someone meant, or nothing.

    Exact first, then punctuation-blind, then a unique prefix or containment.
    Ambiguity returns nothing rather than a guess: acting on the wrong one is
    worse than saying which ones matched.
    """
    for name in existing:
        if name == spoken:
            return name

    wanted = simplify(spoken)
    if not wanted:
        return None

    simple = [(simplify(name), name) for name in existing]

    exact = [name for key, name in simple if key == wanted]
    if len(exact) == 1:
        return exact[0]

    partial = [name for key, name in simple if key.startswith(wanted) or wanted in key]
    return partial[0] if len(partial) == 1 else None
