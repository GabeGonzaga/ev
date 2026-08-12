"""A note's text, as Notes stores it.

Notes keeps a body as HTML, so plain text has to become HTML somewhere.

Not in `adapters.py`: an architecture test forbids that file from assembling
strings at all, and it is right to. An AppleScript source built by
interpolation is one album name away from being a program. This function
builds a *value* -- something that travels as `argv` and is read with
`item n of argv` -- which is the opposite case, and it lives in its own module
so the rule about scripts can stay absolute.
"""

from __future__ import annotations

from html import escape


def html(title: str, body: str | None) -> str:
    """Escaped first, then wrapped.

    A note about `<b>` is about `<b>`, not a note containing bold text. Blank
    lines survive as blank lines: a note that silently reflows what was
    dictated into it is not a record of it.

    The title leads the body because Notes shows a note's first line as its
    title in the list. Setting only the `name` property leaves a note whose
    title and first line disagree.
    """
    lines = [f"<h1>{escape(title)}</h1>"]
    for line in (body or "").splitlines():
        lines.append(
            f"<div>{escape(line)}</div>" if line.strip() else "<div><br></div>"
        )
    return "".join(lines)
