"""Turning what someone typed into an FTS5 query.

FTS5's MATCH argument is a small language: `AND`, `OR`, `NOT`, `NEAR`, `^`,
`*`, `:`, parentheses and quoted phrases. Passing a person's words to it
unchanged means "blonde AND" is a syntax error, "frank ocean:" is a column
filter, and a stray quote is an exception instead of an answer.

So nothing is passed through. Every token is quoted, which makes it a literal,
and the pieces are joined by us. This is the same rule the rest of E.V.
follows at every boundary -- the caller supplies values, never syntax.
"""

from __future__ import annotations

import re

_TOKENS = re.compile(r"[\w']+", re.UNICODE)

MAX_TOKENS = 12
"""A search, not a corpus. Twelve words is more than anyone types and short
enough that the query stays fast on a journal of any size."""


def fts_query(text: str) -> str | None:
    """The MATCH expression for a search box, or `None` for nothing to search.

    Tokens are ANDed: someone typing two words means both. The last one gets a
    prefix match, so "blon" finds "Blonde" while the word is still being
    typed -- and only the last, because prefixing every token makes "a b"
    match most of the journal.
    """
    tokens = _TOKENS.findall(text)[:MAX_TOKENS]
    if not tokens:
        return None

    # A quoted token is a literal string to FTS5. The doubling is how a quote
    # is escaped inside one, and it is why "it's" is a search and not an error.
    quoted = [f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens]
    quoted[-1] = f"{quoted[-1]}*"
    return " AND ".join(quoted)
