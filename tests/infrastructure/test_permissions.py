from __future__ import annotations

import json
from pathlib import Path

import pytest

from ev.application.policy import PermissionLedger, PermissionPolicy, PolicyDecision
from ev.domain.permissions import Permission, PermissionState
from ev.domain.risk import RiskLevel
from ev.infrastructure.macos.applescript import AppleScriptClient, AppleScriptError
from ev.infrastructure.macos.processes import ProcessRunner
from ev.infrastructure.permissions import (
    grants_path,
    load_grants,
    parse_permission,
    reloader,
    save_grants,
)
from tests.conftest import FakeBin


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


def test_an_asserted_permission_is_believed_without_asking_anyone(
    tmp_path: Path,
) -> None:
    """An assertion still counts, and still costs nothing to make.

    It no longer has to be made, though: an undecided permission is now let
    through so macOS can ask (ADR 0032). The difference the file makes is that
    a granted permission is known before the first attempt rather than after
    it.
    """
    path = grants_path(tmp_path)
    save_grants(path, [Permission.APPLE_EVENTS])

    class Guarded:
        name = "music.play"
        risk = RiskLevel.SENSITIVE
        permissions = frozenset({Permission.APPLE_EVENTS})

    unknown = PermissionPolicy(PermissionLedger()).decide(Guarded())
    asserted = PermissionPolicy(PermissionLedger(load_grants(path))).decide(Guarded())

    assert unknown.decision is PolicyDecision.REQUEST_PERMISSION
    assert asserted.decision is PolicyDecision.ALLOW


def test_a_grant_counts_without_a_restart(tmp_path: Path) -> None:
    """The defect this fixes: a daemon read its grants once, at startup.

    Someone granted apple_events, was told it was recorded, and watched the
    next turn refuse anyway -- because the process had been running for half
    an hour. Doing what you were told and nothing happening is worse than
    being refused.
    """
    path = grants_path(tmp_path)
    ledger = PermissionLedger(load_grants(path), refresh=reloader(path))
    policy = PermissionPolicy(ledger)

    class Guarded:
        name = "music.play"
        risk = RiskLevel.SENSITIVE
        permissions = frozenset({Permission.APPLE_EVENTS})

    assert policy.decide(Guarded()).decision is PolicyDecision.REQUEST_PERMISSION

    # The same thing `ev --grant apple_events` does, while this runs.
    save_grants(path, [Permission.APPLE_EVENTS])

    assert policy.decide(Guarded()).decision is PolicyDecision.ALLOW


def test_a_revoked_grant_also_counts_immediately(tmp_path: Path) -> None:
    path = grants_path(tmp_path)
    save_grants(path, [Permission.APPLE_EVENTS])
    ledger = PermissionLedger(load_grants(path), refresh=reloader(path))

    assert ledger.state(Permission.APPLE_EVENTS) is PermissionState.GRANTED

    save_grants(path, [])

    assert ledger.state(Permission.APPLE_EVENTS) is PermissionState.UNDETERMINED


def test_a_missing_file_leaves_the_ledger_alone(tmp_path: Path) -> None:
    ledger = PermissionLedger(
        {Permission.APPLE_EVENTS: PermissionState.GRANTED},
        refresh=reloader(grants_path(tmp_path)),
    )

    # Nothing to read is not the same as "nothing is granted": the host may
    # have reported this, and a missing file must not erase that.
    assert ledger.state(Permission.APPLE_EVENTS) is PermissionState.GRANTED


def test_a_malformed_file_does_not_erase_what_was_granted(tmp_path: Path) -> None:
    path = grants_path(tmp_path)
    save_grants(path, [Permission.APPLE_EVENTS])
    ledger = PermissionLedger(load_grants(path), refresh=reloader(path))
    assert ledger.state(Permission.APPLE_EVENTS) is PermissionState.GRANTED

    path.write_text("{ not json")

    assert ledger.state(Permission.APPLE_EVENTS) is PermissionState.GRANTED


def test_the_refusal_says_how_to_fix_itself(tmp_path: Path) -> None:
    """A refusal is now only for what macOS actually refused.

    And it names the pane rather than a flag: retrying raises no second
    dialog, so the only useful answer is where to change the decision.
    """
    ledger = PermissionLedger({Permission.APPLE_EVENTS: PermissionState.DENIED})
    policy = PermissionPolicy(ledger)

    class Guarded:
        name = "music.play"
        risk = RiskLevel.SENSITIVE
        permissions = frozenset({Permission.APPLE_EVENTS})

    verdict = policy.decide(Guarded())

    assert verdict.decision is PolicyDecision.DENY
    assert verdict.reason is not None
    assert "System Settings > Privacy & Security > Automation" in verdict.reason


# --- what the system itself says -------------------------------------------


@pytest.mark.asyncio
async def test_a_delivered_apple_event_is_proof_of_automation(
    fake_bin: FakeBin,
) -> None:
    """The evidence E.V. was missing.

    An Apple Event that arrived somewhere is the only proof Automation is on,
    and it is a better one than a person asserting it with `--grant`.
    """
    seen: list[tuple[Permission, PermissionState]] = []
    client = AppleScriptClient(ProcessRunner(), report=lambda p, s: seen.append((p, s)))

    await client.run("on run argv\n\treturn 1\nend run")

    assert seen == [(Permission.APPLE_EVENTS, PermissionState.GRANTED)]


@pytest.mark.asyncio
async def test_a_refused_apple_event_is_recorded_as_refused(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_EXIT", "1")
    monkeypatch.setenv(
        "EV_FAKE_STDERR",
        "execution error: Not authorized to send Apple events to Music. (-1743)",
    )
    seen: list[tuple[Permission, PermissionState]] = []
    client = AppleScriptClient(ProcessRunner(), report=lambda p, s: seen.append((p, s)))

    with pytest.raises(AppleScriptError):
        await client.run("on run argv\n\treturn 1\nend run")

    assert seen == [(Permission.APPLE_EVENTS, PermissionState.DENIED)]


@pytest.mark.asyncio
async def test_a_script_that_failed_for_its_own_reasons_says_nothing(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A missing album is not a permission problem, and recording one would
    # turn every typo into a refusal that outlives it.
    monkeypatch.setenv("EV_FAKE_EXIT", "1")
    monkeypatch.setenv("EV_FAKE_STDERR", "execution error: nothing matches Blonde")
    seen: list[tuple[Permission, PermissionState]] = []
    client = AppleScriptClient(ProcessRunner(), report=lambda p, s: seen.append((p, s)))

    with pytest.raises(AppleScriptError):
        await client.run("on run argv\n\treturn 1\nend run")

    assert seen == []


def test_a_grant_learned_at_runtime_survives_the_process(tmp_path: Path) -> None:
    # Learned once, known on the next launch: otherwise every restart asks
    # macOS again, and the first turn after one is the slow one.
    path = grants_path(tmp_path)
    ledger = PermissionLedger(
        persist=lambda granted: save_grants(path, sorted(granted))
    )

    ledger.update(Permission.APPLE_EVENTS, PermissionState.GRANTED)

    assert load_grants(path) == {Permission.APPLE_EVENTS: PermissionState.GRANTED}


def test_a_refusal_is_not_written_down(tmp_path: Path) -> None:
    """TCC can be changed in System Settings at any moment.

    A refusal on disk would outlive the decision that caused it, and E.V.
    would keep refusing something the user had since allowed.
    """
    path = grants_path(tmp_path)
    ledger = PermissionLedger(
        persist=lambda granted: save_grants(path, sorted(granted))
    )

    ledger.update(Permission.CAMERA, PermissionState.DENIED)

    assert not path.exists()
