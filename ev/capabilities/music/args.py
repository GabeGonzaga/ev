"""The schema for the music tools."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


Change = Literal["up", "down", "mute", "unmute"]

STEP = 10
"""How much "louder" is. Ten points is a noticeable change and four presses
across the dial, which is about how often someone says it twice."""


class VolumeArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="An exact volume, 0 to 100. Music's own, not the system's.",
    )

    change: Change | None = Field(
        default=None,
        description="Or a relative change: up, down, mute, unmute.",
    )

    @model_validator(mode="after")
    def _one_or_the_other(self) -> Self:
        # "Set it to 40 and also turn it up" is not a request, and a model
        # sending both should be corrected rather than obeyed in some order.
        if (self.level is None) == (self.change is None):
            raise ValueError("give a level or a change, not both and not neither")
        return self
