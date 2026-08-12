"""The schema for the macro tools."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RunArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=80,
        description="The name of a macro that already exists. Macros are "
        "written to macros.json; nothing creates one by being asked to run it.",
    )
