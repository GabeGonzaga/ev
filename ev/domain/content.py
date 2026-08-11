"""Text a model wrote.

The invariant, from `CLAUDE.md`: generated text may only enter a tool as a
`content`-typed field. It may never become a path, identifier, bundle id,
executable, shortcut name, URL, or any other argument that selects a target.

"Translate this and save it to Notes" means the body is generated and the note
title is not.

`Content` is where that rule stops being a convention. A field typed this way
is declaring that model-written text is acceptable in it; every other field is
declaring that it is not. The marker travels into the generated LLM spec, so
the distinction is visible to anything that reads the schema -- which is what
makes it checkable when tools start feeding each other in phase 4.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

CONTENT_MARKER = "x-ev-content"

Content = Annotated[
    str,
    Field(
        min_length=1,
        max_length=8000,
        json_schema_extra={CONTENT_MARKER: True},
    ),
]
