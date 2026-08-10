from __future__ import annotations

from ev.domain.permissions import Permission, PermissionState
from ev.domain.risk import RiskLevel


# These values are journalled and, from phase 1.5, cross the IPC boundary into
# Rust and TypeScript. Pinning them here makes a rename show up as a decision.
def test_risk_levels_are_stable_wire_values() -> None:
    assert [level.value for level in RiskLevel] == [
        "safe",
        "sensitive",
        "destructive",
    ]


def test_permissions_are_stable_wire_values() -> None:
    assert [permission.value for permission in Permission] == [
        "microphone",
        "camera",
        "accessibility",
        "apple_events",
    ]


def test_permission_states_are_stable_wire_values() -> None:
    assert [state.value for state in PermissionState] == [
        "granted",
        "denied",
        "undetermined",
    ]
