"""What the user is shown before a guarded action runs.

The request is built from *validated* arguments, never from the raw router
output: the user must be asked about the call that would actually execute.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ev.domain.risk import RiskLevel


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool: str
    risk: RiskLevel
    arguments: dict[str, object] = Field(default_factory=dict)
