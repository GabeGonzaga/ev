from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ev.application.policy import (
    PermissionLedger,
    PermissionPolicy,
    PolicyDecision,
)
from ev.domain.permissions import Permission, PermissionState
from ev.domain.results import ToolResult
from ev.domain.risk import RiskLevel
from ev.registry import ToolSpec


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def _never_called(args: NoArgs) -> ToolResult:  # pragma: no cover
    raise AssertionError("the policy must not run the tool")


def spec(
    *,
    name: str = "music.play",
    risk: RiskLevel = RiskLevel.SAFE,
    permissions: frozenset[Permission] = frozenset(),
) -> ToolSpec[NoArgs]:
    return ToolSpec(
        name=name,
        description="",
        args=NoArgs,
        risk=risk,
        handler=_never_called,
        permissions=permissions,
    )


# --- permissions ----------------------------------------------------------


def test_a_tool_needing_nothing_is_allowed() -> None:
    policy = PermissionPolicy(PermissionLedger())

    assert policy.decide(spec()).decision is PolicyDecision.ALLOW


def test_an_undetermined_permission_denies() -> None:
    # Phase 0 has no native host, so nothing is granted and anything declaring
    # a permission cannot run. Denying is the honest answer.
    policy = PermissionPolicy(PermissionLedger())

    verdict = policy.decide(spec(permissions=frozenset({Permission.MICROPHONE})))

    assert verdict.decision is PolicyDecision.DENY
    assert verdict.reason is not None
    assert "microphone" in verdict.reason


def test_a_granted_permission_allows() -> None:
    ledger = PermissionLedger({Permission.APPLE_EVENTS: PermissionState.GRANTED})
    policy = PermissionPolicy(ledger)

    verdict = policy.decide(spec(permissions=frozenset({Permission.APPLE_EVENTS})))

    assert verdict.decision is PolicyDecision.ALLOW


def test_every_declared_permission_must_be_held() -> None:
    ledger = PermissionLedger({Permission.APPLE_EVENTS: PermissionState.GRANTED})
    policy = PermissionPolicy(ledger)

    verdict = policy.decide(
        spec(permissions=frozenset({Permission.APPLE_EVENTS, Permission.CAMERA}))
    )

    assert verdict.decision is PolicyDecision.DENY
    assert verdict.reason is not None
    assert "camera" in verdict.reason
    assert "apple_events" not in verdict.reason


def test_a_denied_permission_denies() -> None:
    ledger = PermissionLedger({Permission.CAMERA: PermissionState.DENIED})
    policy = PermissionPolicy(ledger)

    verdict = policy.decide(spec(permissions=frozenset({Permission.CAMERA})))

    assert verdict.decision is PolicyDecision.DENY


def test_the_ledger_takes_updates_from_the_host() -> None:
    ledger = PermissionLedger()
    policy = PermissionPolicy(ledger)
    guarded = spec(permissions=frozenset({Permission.ACCESSIBILITY}))

    assert policy.decide(guarded).decision is PolicyDecision.DENY

    ledger.update(Permission.ACCESSIBILITY, PermissionState.GRANTED)

    assert policy.decide(guarded).decision is PolicyDecision.ALLOW


# --- risk -----------------------------------------------------------------


def test_destructive_is_confirmed_by_default() -> None:
    policy = PermissionPolicy(PermissionLedger())

    verdict = policy.decide(spec(risk=RiskLevel.DESTRUCTIVE))

    assert verdict.decision is PolicyDecision.CONFIRM
    assert verdict.reason is not None
    assert "destructive" in verdict.reason


def test_sensitive_runs_by_default() -> None:
    # The permission gate is what guards a sensitive tool. Confirming every
    # music.play would make the assistant unusable on the voice path.
    policy = PermissionPolicy(PermissionLedger())

    verdict = policy.decide(spec(risk=RiskLevel.SENSITIVE))

    assert verdict.decision is PolicyDecision.ALLOW


def test_a_cautious_threshold_confirms_sensitive_too() -> None:
    policy = PermissionPolicy(PermissionLedger(), confirm_at=RiskLevel.SENSITIVE)

    assert (
        policy.decide(spec(risk=RiskLevel.SENSITIVE)).decision is PolicyDecision.CONFIRM
    )
    assert policy.decide(spec(risk=RiskLevel.SAFE)).decision is PolicyDecision.ALLOW


def test_a_missing_permission_outranks_the_risk_threshold() -> None:
    # Not "ask the user and then fail": there is nothing to ask about.
    policy = PermissionPolicy(PermissionLedger())

    verdict = policy.decide(
        spec(risk=RiskLevel.DESTRUCTIVE, permissions=frozenset({Permission.CAMERA}))
    )

    assert verdict.decision is PolicyDecision.DENY
