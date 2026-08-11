"""One line of the audit trail, read back.

The journal has been write-only until now, deliberately: nothing read it, and
a read API with no reader is a guess about what someone will want. Phase 3
wants history, so this is the shape it gets -- and it is the same shape in the
core, on the wire and in the UI, for the reason ADR 0015 gives.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ev.domain.risk import RiskLevel


class JournalEntry(BaseModel):
    """What E.V. did, once."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int
    recorded_at: str = Field(description="ISO 8601, UTC, stamped when it happened.")
    tool: str
    risk: RiskLevel
    ok: bool
    arguments: dict[str, object] = Field(default_factory=dict)
    speech: str | None = None
    error_code: str | None = None
    error_message: str | None = None
