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
        #
        # The scheme sentence is there because of a measurement: a model that
        # routed "look at example.com/pricing in my browser" perfectly still
        # wrote the bare domain, which HttpUrl refuses, so a correct routing
        # died as INVALID_ARGUMENTS. See `make eval`.
        description=(
            "A full http or https URL, including the scheme, "
            "for example https://example.com/pricing. Other schemes are "
            "refused, and a bare domain without https:// is refused."
        ),
    )
