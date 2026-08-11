"""The schema for the language tools.

`text` is the only `Content` field in the project: it is the one argument that
is allowed to be, or become, model-written prose. `to` is not -- it selects
what happens, so it is a closed set.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ev.domain.content import Content

Language = Literal["pt-PT", "en", "es", "fr", "de", "it"]
"""pt-PT, never pt-BR. Multilingual models default to Brazilian, so the code
that reaches the prompt has to be explicit."""


class TranslateArgs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Content = Field(description="The text to translate, exactly as given.")
    to: Language = Field(description="The language to translate into.")
