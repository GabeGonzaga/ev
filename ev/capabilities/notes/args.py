"""The schema for the notes tools.

This is the capability `CLAUDE.md` uses to state the generation-path rule:
"translate this and save it to Notes" means the body is generated and the note
title is not. So `body` is `Content` and `title` is not, and the marker says
which is which to anything reading the schema.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ev.domain.content import Content


class CreateArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "The note's title, in the user's own words. Not generated, not "
            "translated, not summarised."
        ),
    )

    body: Content | None = Field(
        default=None,
        description="The note's text. This is the only field that may be written.",
    )

    folder: str | None = Field(
        default=None,
        max_length=200,
        # Resolved against the folders that exist, like a playlist name. A
        # folder that does not exist is refused rather than created: making
        # folders by mishearing one is how a library becomes a mess.
        description=(
            "An existing folder in Notes. Leave it out for the default folder."
        ),
    )
