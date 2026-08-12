"""The schema for the reminders tools.

The one new thing here is a date. Everything else E.V. takes as an argument is
a name someone said; a due date is a value the model has to *compute* -- "amanhã
às nove" is not in the utterance, it is derived from it and from what day it is.

So `due` is a `datetime`, parsed and bounded by Pydantic before anything sees
it, and the router is told what today is (ADR 0027). A string would have made
"tomorrow" a problem for AppleScript to solve.

There is no body field. There was one, and the model filled it with the request
it had just been given -- and once with a word that was in neither. A reminder
is a line and a time; the field that holds written text is `notes.create`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(
        min_length=1,
        max_length=200,
        description="What to be reminded of, in the user's own words.",
    )

    due: datetime | None = Field(
        default=None,
        description=(
            "When it is due, ISO 8601 in local time, for example "
            "2026-08-13T09:00. Leave it out for a reminder with no date."
        ),
    )

    list: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "An existing list in Reminders. Leave it out for the default list."
        ),
    )
