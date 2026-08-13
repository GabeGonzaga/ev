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

    editions = _editions(spoken, existing)
    if editions:
        return editions

    contained = [name for key, name in simple if wanted in key]
    return contained[0] if len(contained) == 1 else None


_QUALIFIER = ("(", "[", "-", "/", ",", ":")
"""What a music library puts before an edition.

`Here Comes the Sun (2019 Mix)`, `(Take 9)`, `(feat. dodie)` -- three
recordings of one song. `Jazz Classics` and `Jazz Nights` are two playlists.
The difference is the character after the words that were actually said.
"""


def _editions(spoken: str, existing: list[str]) -> str | None:
    """The plainest of several recordings of the same thing.

    Names that all begin with what was said and then open a parenthesis, a
    bracket or a dash are editions: a remaster, a live take, a version with a
    guest. Any of them answers the request, so the shortest does -- it is the
    one without the qualifier.

    Names that continue with an ordinary word are different things, and those
    stay ambiguous.
    """
    wanted = " ".join(spoken.casefold().split())
    if not wanted:
        return None

    matches: list[str] = []
    for name in existing:
        plain = " ".join(name.casefold().split())
        if not plain.startswith(wanted):
            continue
        rest = plain[len(wanted) :].lstrip()
        if rest and not rest.startswith(_QUALIFIER):
            # An ordinary word follows, so these are different things and not
            # editions of one. One of them being a different thing is enough:
            # the whole set goes back to being ambiguous.
            return None
        matches.append(name)

    return min(matches, key=_canonical) if matches else None


_ALTERNATE = (
    "take",
    "demo",
    "rehearsal",
    "outtake",
    "instrumental",
    "live",
    "session",
    "remix",
    "karaoke",
)
"""Qualifiers that name a different recording rather than a different master.

Asking for `Here Comes the Sun` and getting `(Take 9)` is not the song anyone
means; `(2019 Mix)` is. Sorting by length alone picked the outtake, because
`Take 9` is shorter than `2019 Mix`."""


def _canonical(name: str) -> tuple[int, int]:
    """How much like the plain version a name is: alternates last, then the
    shortest, which is the one carrying the least explanation."""
    plain = name.casefold()
    return (any(word in plain for word in _ALTERNATE), len(name))
