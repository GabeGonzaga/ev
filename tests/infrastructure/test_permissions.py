from __future__ import annotations

import json
from pathlib import Path

import pytest

from ev.application.policy import PermissionLedger, PermissionPolicy, PolicyDecision
from ev.domain.permissions import Permission, PermissionState
from ev.domain.risk import RiskLevel
from ev.infrastructure.permissions import (
    grants_path,
    load_grants,
    parse_permission,
    save_grants,
)


def test_no_file_means_nothing_is_asserted(tmp_path: Path) -> None:
    assert load_grants(grants_path(tmp_path)) == {}


def test_grants_round_trip(tmp_path: Path) -> None:
    path = grants_path(tmp_path)

    save_grants(path, [Permission.APPLE_EVENTS, Permission.ACCESSIBILITY])

    assert load_grants(path) == {
        Permission.APPLE_EVENTS: PermissionState.GRANTED,
        Permission.ACCESSIBILITY: PermissionState.GRANTED,
    }


def test_the_file_is_readable_by_a_person(tmp_path: Path) -> None:
    path = grants_path(tmp_path)

    save_grants(path, [Permission.APPLE_EVENTS])

    assert json.loads(path.read_text()) == {"granted": ["apple_events"]}


def test_a_typo_is_an_error_not_a_silent_skip(tmp_path: Path) -> None:
    # Skipping it would leave the user believing they asserted something
    # they did not, and the failure would surface much later as a denial.
    path = grants_path(tmp_path)
    path.write_text(json.dumps({"granted": ["apple_event"]}))

    with pytest.raises(ValueError, match="unknown permission 'apple_event'"):
        load_grants(path)


def test_a_malformed_file_says_what_it_expected(tmp_path: Path) -> None:
    path = grants_path(tmp_path)
    path.write_text(json.dumps({"granted": "apple_events"}))

    with pytest.raises(ValueError, match="must be a list"):
        load_grants(path)


def test_parse_permission_names_the_known_ones() -> None:
    with pytest.raises(ValueError, match="microphone"):
        parse_permission("mic")


def test_an_asserted_permission_makes_a_guarded_tool_reachable(
    tmp_path: Path,
) -> None:
    # The whole point: without this, every AppleScript tool is denied before
    # macOS is ever asked.
    path = grants_path(tmp_path)
    save_grants(path, [Permission.APPLE_EVENTS])

    class Guarded:
        name = "music.play"
        risk = RiskLevel.SENSITIVE
        permissions = frozenset({Permission.APPLE_EVENTS})

    denied = PermissionPolicy(PermissionLedger()).decide(Guarded())
    allowed = PermissionPolicy(PermissionLedger(load_grants(path))).decide(Guarded())

    assert denied.decision is PolicyDecision.DENY
    assert allowed.decision is PolicyDecision.ALLOW
