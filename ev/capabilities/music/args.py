"""The schema for the music tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["album", "track", "playlist"]


class PlayArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=200,
        description="The name of the album, track or playlist, exactly as it "
        "appears in the library.",
    )

    kind: Kind = Field(
        # Deliberately required. "Play Blonde" is ambiguous between an album
        # and a track, and the caller resolving it explicitly is better than a
        # default quietly picking one and playing the wrong thing.
        description="What the name refers to.",
    )
