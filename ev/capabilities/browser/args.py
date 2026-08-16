"""The schema for the browser tools.

`HttpUrl` is doing security work, not tidiness. `open(1)` dispatches any scheme
an installed application has registered -- `file://`, `mailto:`, `x-apple-*`,
whatever a third-party app claimed -- so an unconstrained string here would let
the router select a target far outside the browser. http and https only.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Where = Literal["tab", "window"]
"""A tab in whatever is already open, or a small window of its own.

Both are the browser opening the page. E.V. never renders it: an explicit user
action may open an internet resource in the user's browser (invariant 10), and
the difference between these two is the shape of the browser's window, not who
did the fetching.
"""


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

    where: Where = Field(
        default="tab",
        description=(
            "'tab' opens it as a normal tab. 'window' asks the browser for a "
            "small window of its own, placed at the side of the screen."
        ),
    )
