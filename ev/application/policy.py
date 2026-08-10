"""May this call run, and must the user be asked first.

The policy reads two things: whether the TCC permissions a tool declares are
actually held, and how much damage the tool can do. It never probes the system
for either -- permission state is reported by the signed native host through
typed events (invariant 7), and risk is declared per tool.

The *confidence* threshold is not here. It applies to a `Resolution` before the
registry is reached, and no tier produces a confidence below 1.0 until the model
router lands, so it is phase 1 work.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict

from ev.domain.permissions import Permission, PermissionState
from ev.domain.risk import RiskLevel


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"
    """Ask the user first. A DESTRUCTIVE tool is confirmed whatever the policy
    answers -- see `Registry.call()`."""


class PolicyVerdict(BaseModel):
    """The decision plus why, so a refusal can say something useful."""

    model_config = ConfigDict(frozen=True)

    decision: PolicyDecision
    reason: str | None = None

    @classmethod
    def allow(cls) -> Self:
        return cls(decision=PolicyDecision.ALLOW)

    @classmethod
    def deny(cls, reason: str) -> Self:
        return cls(decision=PolicyDecision.DENY, reason=reason)

    @classmethod
    def confirm(cls, reason: str) -> Self:
        return cls(decision=PolicyDecision.CONFIRM, reason=reason)


class Guarded(Protocol):
    """The part of a `ToolSpec` the policy reads.

    Declared structurally so `ev/application/` does not import the registry,
    which imports this module. Read-only: deciding never mutates the spec.
    """

    @property
    def name(self) -> str: ...

    @property
    def risk(self) -> RiskLevel: ...

    @property
    def permissions(self) -> frozenset[Permission]: ...


class PermissionLedger:
    """What the native host last reported about each TCC permission.

    Phase 0 has no native host, so everything is UNDETERMINED and any tool
    declaring a permission cannot run. That is the honest state of the machine,
    not a gap to paper over with an optimistic default.
    """

    def __init__(
        self, states: Mapping[Permission, PermissionState] | None = None
    ) -> None:
        self._states: dict[Permission, PermissionState] = dict(states or {})

    def state(self, permission: Permission) -> PermissionState:
        return self._states.get(permission, PermissionState.UNDETERMINED)

    def update(self, permission: Permission, state: PermissionState) -> None:
        """Called from a `permission.changed` event in phase 1.5."""
        self._states[permission] = state

    def withheld(self, permissions: Iterable[Permission]) -> list[Permission]:
        return sorted(
            permission
            for permission in permissions
            if self.state(permission) is not PermissionState.GRANTED
        )


_ORDER = {RiskLevel.SAFE: 0, RiskLevel.SENSITIVE: 1, RiskLevel.DESTRUCTIVE: 2}


class PermissionPolicy:
    """The default policy: run what is permitted, ask above a risk threshold."""

    def __init__(
        self,
        ledger: PermissionLedger,
        *,
        confirm_at: RiskLevel = RiskLevel.DESTRUCTIVE,
    ) -> None:
        self._ledger = ledger
        self._confirm_at = confirm_at

    def decide(self, spec: Guarded) -> PolicyVerdict:
        withheld = self._ledger.withheld(spec.permissions)
        if withheld:
            missing = ", ".join(permission.value for permission in withheld)
            return PolicyVerdict.deny(
                f"{spec.name} needs permission not granted: {missing}"
            )

        if _ORDER[spec.risk] >= _ORDER[self._confirm_at]:
            return PolicyVerdict.confirm(f"{spec.name} is {spec.risk.value}")

        return PolicyVerdict.allow()
