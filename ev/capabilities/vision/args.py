"""The schema for the vision tool.

There is no field here that names an image, and that is the design. The frame
was captured by a person pressing a button; the model is answering a question
about it, not choosing what to look at. `CLAUDE.md` invariant 8 -- "neither may
be started by ambiguous model inference" -- is enforced by the absence.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ev.domain.content import Content


class LookArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question: Content | None = Field(
        default=None,
        description=(
            "What to answer about what the camera sees, in the user's own "
            "words. Leave it out to describe the scene."
        ),
    )
