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

    Exact first, then punctuation-blind, then the shortest name that *starts*
    with what was said, and only then a unique containment. Ambiguity returns
    nothing rather than a guess: acting on the wrong one is worse than saying
    which ones matched.

    The prefix rule is what a music library taught us. "Kendrick" matches six
    artists -- `Kendrick Lamar`, and five collaborations crediting him -- and
    an earlier version called that ambiguous and refused. Nobody asking for
    Kendrick means `Future, Metro Boomin & Kendrick Lamar`. The shortest name
    that begins with what was said is the one they meant, and a credit that
    merely contains it is not a candidate while a prefix exists.
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

    # `21st century breakdown` for `21st Century Breakdown (Deluxe Edition)`,
    # and `kendrick` for `Kendrick Lamar`. Shortest, because the extra words
    # in the longer ones are the ones nobody said.
    prefixed = sorted(
        ((key, name) for key, name in simple if key.startswith(wanted)),
        key=lambda pair: len(pair[0]),
    )
    if prefixed:
        shortest, name = prefixed[0]
        # The shortest only wins when it begins every other match: `Kendrick
        # Lamar` starts `Kendrick Lamar & SZA`, so they are one artist said at
        # two lengths. `Jazz Classics` and `Jazz Nights` are two playlists, and
        # taking the shorter would be choosing by coin toss.
        if all(other.startswith(shortest) for other, _ in prefixed):
            return name

    contained = [name for key, name in simple if wanted in key]
    return contained[0] if len(contained) == 1 else None
