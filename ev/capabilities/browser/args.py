"""The schema for the browser tools.

`HttpUrl` is doing security work, not tidiness. `open(1)` dispatches any scheme
an installed application has registered -- `file://`, `mailto:`, `x-apple-*`,
whatever a third-party app claimed -- so an unconstrained string here would let
the router select a target far outside the browser. http and https only.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class OpenUrlArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: HttpUrl = Field(
        # The description reaches the model in the generated spec; the type is
        # what enforces it. Both come from this one declaration.
        description="An http or https URL. Other schemes are refused.",
    )
