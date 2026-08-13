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

from collections.abc import Callable, Iterable, Mapping
from enum import StrEnum
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict

from ev.domain.permissions import Permission, PermissionState
from ev.domain.resolution import Resolution
from ev.domain.risk import RiskLevel


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"
    """Ask the user first. A DESTRUCTIVE tool is confirmed whatever the policy
    answers -- see `Registry.call()`."""

    REQUEST_PERMISSION = "request_permission"
    """Never asked for, so let macOS ask.

    E.V. cannot raise a TCC prompt. Only the attempt can, and refusing before
    the attempt is why `--grant` existed: the user was made to assert a
    permission by hand so that E.V. would stop standing between them and the
    dialog. So a permission nobody has decided yet is not a refusal -- the call
    goes through, macOS answers, and whatever it says is recorded.

    A permission that was *refused* still denies here. Trying again produces no
    prompt, only the same silent failure, and the useful answer is where to
    change it."""


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

    @classmethod
    def request(cls, reason: str) -> Self:
        return cls(decision=PolicyDecision.REQUEST_PERMISSION, reason=reason)


class ConfidenceDecision(StrEnum):
    ACCEPT = "accept"
    CLARIFY = "clarify"
    """Understood something, but not well enough to act on it unasked."""

    REFUSE = "refuse"


class ConfidencePolicy:
    """What to do with a proposal the model is not sure about.

    Tier 0 and tier 1 answer at 1.0 and sail through. This exists for tier 2,
    where confidence is the model's own opinion of itself -- which is worth
    something and is not worth trusting alone. A model asked something no tool
    can do has been observed inventing a plausible call and rating it 0.5, so
    the middle band asks rather than acts.
    """

    def __init__(self, *, accept_at: float = 0.7, clarify_at: float = 0.4) -> None:
        if clarify_at > accept_at:
            raise ValueError("clarify_at must not exceed accept_at")
        self._accept_at = accept_at
        self._clarify_at = clarify_at

    def decide(self, resolution: Resolution) -> ConfidenceDecision:
        if resolution.confidence >= self._accept_at:
            return ConfidenceDecision.ACCEPT
        if resolution.confidence >= self._clarify_at:
            return ConfidenceDecision.CLARIFY
        return ConfidenceDecision.REFUSE


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
        self,
        states: Mapping[Permission, PermissionState] | None = None,
        refresh: Callable[[], Mapping[Permission, PermissionState] | None]
        | None = None,
        persist: Callable[[set[Permission]], None] | None = None,
    ) -> None:
        self._persist = persist
        self._states: dict[Permission, PermissionState] = dict(states or {})
        # Asserting a permission and then having to restart the daemon for it
        # to count is a footgun: the user did the thing they were told to do
        # and nothing happened. When a source is given, it is consulted before
        # every answer, and it reports only when something changed.
        self._refresh = refresh

    def _reload(self) -> None:
        if self._refresh is None:
            return
        fresh = self._refresh()
        if fresh is not None:
            self._states = dict(fresh)

    def state(self, permission: Permission) -> PermissionState:
        self._reload()
        return self._states.get(permission, PermissionState.UNDETERMINED)

    def update(self, permission: Permission, state: PermissionState) -> None:
        """What the system just said about a permission.

        Reported by the host, or learned from an attempt that macOS answered.
        A grant is written down so the next run starts knowing it; a refusal is
        not, because TCC can be changed in System Settings at any moment and a
        refusal on disk would outlive the decision that caused it.
        """
        if self._states.get(permission) is state:
            return

        self._states[permission] = state
        if state is PermissionState.GRANTED and self._persist is not None:
            self._persist(
                {
                    name
                    for name, held in self._states.items()
                    if held is PermissionState.GRANTED
                }
            )

    def withheld(self, permissions: Iterable[Permission]) -> list[Permission]:
        return sorted(
            permission
            for permission in permissions
            if self.state(permission) is not PermissionState.GRANTED
        )

    def refused(self, permissions: Iterable[Permission]) -> list[Permission]:
        """The ones macOS has actually said no to."""
        return sorted(
            permission
            for permission in permissions
            if self.state(permission) is PermissionState.DENIED
        )


_ORDER = {RiskLevel.SAFE: 0, RiskLevel.SENSITIVE: 1, RiskLevel.DESTRUCTIVE: 2}

SETTINGS = {
    Permission.MICROPHONE: "Microphone",
    Permission.CAMERA: "Camera",
    Permission.ACCESSIBILITY: "Accessibility",
    Permission.APPLE_EVENTS: "Automation",
}
"""Where in System Settings each one is changed. A refusal that does not say
where to undo it is a dead end, and the pane names are not guessable."""


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
        refused = self._ledger.refused(spec.permissions)
        if refused:
            missing = ", ".join(permission.value for permission in refused)
            return PolicyVerdict.deny(
                f"{spec.name} needs {missing}, and macOS has refused it. "
                f"System Settings > Privacy & Security > {SETTINGS[refused[0]]}"
            )

        # Nobody has decided this one yet, so let the system be the one to ask.
        # Reported before the risk, because what the verdict says should be the
        # most specific true thing about the call. A destructive tool is
        # confirmed either way: `Registry.call()` enforces that itself, so that
        # a policy bug cannot let one run unasked.
        undecided = self._ledger.withheld(spec.permissions)
        if undecided:
            missing = ", ".join(permission.value for permission in undecided)
            return PolicyVerdict.request(
                f"{spec.name} needs {missing}, which macOS has not been asked for yet"
            )

        if _ORDER[spec.risk] >= _ORDER[self._confirm_at]:
            return PolicyVerdict.confirm(f"{spec.name} is {spec.risk.value}")

        return PolicyVerdict.allow()
