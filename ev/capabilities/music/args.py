"""The schema for the music tools."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Kind = Literal["album", "artist", "track", "playlist"]

Action = Literal["pause", "resume", "next", "previous", "stop"]
"""What the buttons on a music app do. A closed set, because "control the
music" with a free-text verb is a shell by another name."""


class PlayArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "The name of the album, artist, track or playlist, as the user "
            "said it. It is matched against the library, so a partial name "
            "is fine: 'kendrick' finds Kendrick Lamar."
        ),
    )

    kind: Kind = Field(
        # Deliberately required. "Play Blonde" is ambiguous between an album
        # and a track, and the caller resolving it explicitly is better than a
        # default quietly picking one and playing the wrong thing.
        #
        # Being wrong is survivable, though: a name that matches nothing of
        # the kind that was asked for is looked for among the others before
        # E.V. gives up.
        description="What the name refers to: album, artist, track or playlist.",
    )


Setting = Literal["shuffle", "repeat"]
"""The two switches on a music app that stay where you put them. Everything
else in `Action` happens once; these are state."""

Switch = Literal["on", "off", "toggle", "one"]
"""What to do with one of them.

`toggle` is the default because that is what a button is: pressing it once
turns the thing on, pressing it again turns it off. Saying "shuffle" is
pressing the button, and the current state is read from Music rather than
remembered here -- E.V. is not the only thing that touches these.

`one` is repeat's third position. Music's `song repeat` is off, all or one,
and "repeat this song" is a thing people say.
"""


class ModeArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    setting: Setting = Field(description="Which switch: shuffle or repeat.")

    state: Switch = Field(
        default="toggle",
        description=(
            "on, off, or toggle to flip it. Use 'one' with repeat to repeat "
            "the current track rather than the whole queue."
        ),
    )

    @model_validator(mode="after")
    def _one_is_a_repeat_position(self) -> Self:
        # Shuffling "one" is not a thing, and a model that asks for it has
        # misunderstood the question rather than found a hidden feature.
        if self.setting == "shuffle" and self.state == "one":
            raise ValueError("'one' is a repeat position, not a shuffle state")
        return self


class NowPlayingArgs(BaseModel):
    """Nothing to ask for. What is playing is what is playing."""

    model_config = ConfigDict(frozen=True, extra="forbid")


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
