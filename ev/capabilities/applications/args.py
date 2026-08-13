"""The schema for the application tools.

`name` is a name, not a path and not a bundle id. It is matched against what is
installed before anything is launched, so what the model supplies is a guess to
be resolved rather than a target to be obeyed.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApplicationArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=100,
        description=(
            "The application's name as it appears in the Applications folder, "
            "for example Safari or Visual Studio Code."
        ),
    )
