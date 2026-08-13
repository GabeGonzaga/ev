"""What the user is shown before a guarded action runs.

The request is built from *validated* arguments, never from the raw router
output: the user must be asked about the call that would actually execute.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ev.domain.access import Assurance
from ev.domain.risk import RiskLevel


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool: str
    risk: RiskLevel
    arguments: dict[str, object] = Field(default_factory=dict)

    application: str | None = None
    """Which application would be touched, when one would. The user set a level
    for it, so the question should say which one is being answered about."""

    assurance: Assurance = Assurance.ACK
    """How the yes has to be given. A surface that cannot satisfy it must
    decline rather than substitute a weaker one: a click is not a password, and
    silently accepting one for the other is the whole failure this exists to
    prevent."""


def satisfiable(request: ConfirmationRequest, asker: object) -> bool:
    """Whether this surface can give the answer that was asked for.

    A click in a panel proves someone is at the machine. It does not prove who
    they are, and an application set to `verify` asked for the second thing.
    Only a surface that can raise macOS's own authentication -- the signed app,
    and nothing else -- may answer those. A surface that cannot must decline
    rather than substitute a weaker yes, which is the one failure the level
    exists to prevent.

    Asked of the surface rather than declared by it, because the surfaces are
    in infrastructure and this rule is not theirs to soften.
    """
    if request.assurance in {Assurance.NONE, Assurance.ACK}:
        return True
    return bool(getattr(asker, "verifies", False))
