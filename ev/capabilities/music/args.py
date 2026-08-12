"""The schema for the music tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["album", "track", "playlist"]

Action = Literal["pause", "resume", "next", "previous", "stop"]
"""What the buttons on a music app do. A closed set, because "control the
music" with a free-text verb is a shell by another name."""


class PlayArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=200,
        description="The name of the album, track or playlist.",
    )

    kind: Kind = Field(
        # Deliberately required. "Play Blonde" is ambiguous between an album
        # and a track, and the caller resolving it explicitly is better than a
        # default quietly picking one and playing the wrong thing.
        description="What the name refers to.",
    )


class ControlArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Action = Field(description="Pause, resume, skip, go back, or stop.")


class VolumeArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: int = Field(
        ge=0,
        le=100,
        description="Music's own volume, 0 to 100. Not the system volume.",
    )
