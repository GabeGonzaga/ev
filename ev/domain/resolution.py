"""What a router proposes.

Every tier returns this same shape: tier 0 and tier 1 from `router/static.py`,
tier 2 from the model in phase 1. That is the seam described in CLAUDE.md --
`Assistant.handle()` gains one fallback branch and nothing else changes.

A Resolution is a *proposal*. It has not been validated against the tool's args
model, it has not passed policy, and `arguments` may be raw model output. It
must not reach an adapter except through `Registry.call()`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Resolution(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool: str
    arguments: dict[str, object] = Field(default_factory=dict)
    """Unvalidated. Pydantic validation against the tool's args model comes next."""

    confidence: float = Field(ge=0.0, le=1.0)
    """Below the policy threshold this is refused or escalated, never guessed at."""

    response: str | None = None
    """Optional user-facing text. Generated content, so it may never select a
    target: not a path, identifier, bundle id, executable or shortcut name."""
