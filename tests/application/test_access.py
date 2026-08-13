"""Four levels, per application, and how they meet the risk of a tool."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from ev.application.applications import (
    VERIFIED_FOR,
    ApplicationLedger,
    applications_path,
    load_levels,
    reloader,
    save_levels,
)
from ev.application.confirmation import ConfirmationRequest, satisfiable
from ev.application.policy import PermissionLedger, PermissionPolicy, PolicyDecision
from ev.domain.access import AccessLevel, Assurance, strongest
from ev.domain.permissions import Permission, PermissionState
from ev.domain.results import ToolResult
from ev.domain.risk import RiskLevel
from ev.registry import ToolSpec


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def _never_called(args: NoArgs) -> ToolResult:  # pragma: no cover
    raise AssertionError("the policy decides; nothing here runs")


def spec(
    *,
    risk: RiskLevel = RiskLevel.SENSITIVE,
    permissions: frozenset[Permission] = frozenset(),
    assurance: Assurance = Assurance.NONE,
) -> ToolSpec[NoArgs]:
    return ToolSpec(
        name="mail.send",
        description="",
        args=NoArgs,
        risk=risk,
        handler=_never_called,
        permissions=permissions,
        assurance=assurance,
    )


def policy(**levels: AccessLevel) -> PermissionPolicy:
    return PermissionPolicy(
        PermissionLedger({Permission.APPLE_EVENTS: PermissionState.GRANTED}),
        applications=ApplicationLedger(dict(levels)),
    )


# --- the four levels ------------------------------------------------------


def test_open_acts_without_asking() -> None:
    verdict = policy(mail=AccessLevel.OPEN).decide(spec(), "Mail")

    assert verdict.decision is PolicyDecision.ALLOW


def test_ask_asks_every_time() -> None:
    verdict = policy(mail=AccessLevel.ASK).decide(spec(), "Mail")

    assert verdict.decision is PolicyDecision.CONFIRM
    assert verdict.assurance is Assurance.ACK
    assert verdict.reason is not None
    assert "Mail" in verdict.reason


def test_verify_asks_macos_rather_than_the_panel() -> None:
    # Not a dialog E.V. draws. A program that renders its own password box is
    # teaching people to type their password into programs.
    verdict = policy(mail=AccessLevel.VERIFY).decide(spec(), "Mail")

    assert verdict.decision is PolicyDecision.CONFIRM
    assert verdict.assurance is Assurance.OWNER


def test_blocked_refuses_and_offers_nothing() -> None:
    """No assurance on a refusal.

    An assurance here would turn "no" into a challenge to be got around, which
    is the opposite of what the level says.
    """
    verdict = policy(mail=AccessLevel.BLOCKED).decide(spec(), "Mail")

    assert verdict.decision is PolicyDecision.DENY
    assert verdict.assurance is Assurance.NONE


def test_an_application_nobody_decided_about_is_asked_about() -> None:
    # Not `open`, which would act on something never considered; not
    # `blocked`, which would mean nothing works until a file is edited.
    verdict = policy().decide(spec(), "Photos")

    assert verdict.decision is PolicyDecision.CONFIRM
    assert verdict.assurance is Assurance.ACK


def test_a_tool_that_touches_no_application_is_unaffected() -> None:
    # `language.translate` asks a model a question. There is no application to
    # have an opinion about.
    verdict = policy().decide(spec(risk=RiskLevel.SAFE), None)

    assert verdict.decision is PolicyDecision.ALLOW


# --- the two floors meet --------------------------------------------------


def test_trusting_an_application_does_not_make_a_tool_reversible() -> None:
    """The case the whole design is for.

    Finder can be `open` -- it is used constantly -- and emptying the Trash
    still has to be verified, because what makes that dangerous is the tool,
    not the application.
    """
    verdict = policy(finder=AccessLevel.OPEN).decide(
        spec(risk=RiskLevel.DESTRUCTIVE), "Finder"
    )

    assert verdict.decision is PolicyDecision.CONFIRM
    assert verdict.assurance is Assurance.OWNER


def test_a_harmless_tool_gets_no_pass_into_a_locked_application() -> None:
    verdict = policy(mail=AccessLevel.VERIFY).decide(spec(risk=RiskLevel.SAFE), "Mail")

    assert verdict.assurance is Assurance.OWNER


def test_a_tool_can_demand_more_than_its_application_asks() -> None:
    # Sending a message speaks to another person in the user's name, and no
    # amount of trusting the application makes that undoable.
    verdict = policy(messages=AccessLevel.OPEN).decide(
        spec(assurance=Assurance.OWNER_AND_PASSWORD), "Messages"
    )

    assert verdict.assurance is Assurance.OWNER_AND_PASSWORD


def test_the_strongest_wins_whichever_side_it_came_from() -> None:
    assert strongest(Assurance.ACK, Assurance.OWNER) is Assurance.OWNER
    assert strongest(Assurance.NONE, Assurance.ACK) is Assurance.ACK
    assert (
        strongest(Assurance.OWNER, Assurance.OWNER_AND_PASSWORD)
        is Assurance.OWNER_AND_PASSWORD
    )


def test_a_blocked_application_outranks_everything() -> None:
    # Including a permission that is held and a tool that is safe.
    verdict = policy(mail=AccessLevel.BLOCKED).decide(spec(risk=RiskLevel.SAFE), "Mail")

    assert verdict.decision is PolicyDecision.DENY


# --- the file -------------------------------------------------------------


def test_the_level_survives_a_restart(tmp_path: Path) -> None:
    path = applications_path(tmp_path)
    save_levels(path, {"mail": AccessLevel.BLOCKED, "music": AccessLevel.OPEN})

    assert load_levels(path) == {
        "mail": AccessLevel.BLOCKED,
        "music": AccessLevel.OPEN,
    }


def test_the_name_is_matched_whatever_the_capitals(tmp_path: Path) -> None:
    # A level that stops applying because someone typed `mail` is a level that
    # silently grants what it was written to refuse.
    ledger = ApplicationLedger({"visual studio code": AccessLevel.BLOCKED})

    assert ledger.level("Visual Studio Code") is AccessLevel.BLOCKED


def test_an_unknown_level_is_an_error_not_a_shrug(tmp_path: Path) -> None:
    path = applications_path(tmp_path)
    path.write_text('{"applications": {"Mail": "maybe"}}', encoding="utf-8")

    with pytest.raises(ValueError, match="maybe"):
        load_levels(path)


def test_a_level_counts_without_a_restart(tmp_path: Path) -> None:
    # The same defect the permission grants had: a daemon that read the file
    # once, and a user whose decision did nothing until they restarted it.
    path = applications_path(tmp_path)
    ledger = ApplicationLedger(load_levels(path), refresh=reloader(path))

    assert ledger.level("Mail") is AccessLevel.ASK

    save_levels(path, {"mail": AccessLevel.BLOCKED})

    assert ledger.level("Mail") is AccessLevel.BLOCKED


def test_an_answer_is_remembered(tmp_path: Path) -> None:
    path = applications_path(tmp_path)
    ledger = ApplicationLedger(persist=lambda known: save_levels(path, known))

    ledger.remember("Photos", AccessLevel.OPEN)

    assert load_levels(path) == {"photos": AccessLevel.OPEN}


# --- what a surface may answer --------------------------------------------


def request(assurance: Assurance) -> ConfirmationRequest:
    return ConfirmationRequest(
        tool="mail.send",
        risk=RiskLevel.SENSITIVE,
        application="Mail",
        assurance=assurance,
    )


class Panel:
    """A surface with buttons and nothing else."""


class SignedApp:
    """A surface that can raise macOS's own authentication."""

    verifies = True


def test_a_click_answers_a_click() -> None:
    assert satisfiable(request(Assurance.ACK), Panel())


def test_a_click_does_not_answer_a_password() -> None:
    """The failure the whole level exists to prevent.

    A button in a window E.V. drew proves someone is at the machine. It does
    not prove who, and `verify` asked for the second thing.
    """
    assert not satisfiable(request(Assurance.OWNER), Panel())


def test_only_a_surface_that_can_verify_may_answer_verify() -> None:
    assert satisfiable(request(Assurance.OWNER), SignedApp())
    assert satisfiable(request(Assurance.OWNER_AND_PASSWORD), SignedApp())


# --- one verification covers a burst --------------------------------------


def test_a_verification_covers_the_next_few_minutes() -> None:
    """The complaint this fixes.

    Music at `verify` asked for a fingerprint to play an album, again to skip
    a track, again to pause. Three prompts for one intent teaches people to
    authenticate without reading, which is the habit the prompt exists to
    interrupt.
    """
    ledger = ApplicationLedger({"music": AccessLevel.VERIFY})
    guarded = PermissionPolicy(
        PermissionLedger({Permission.APPLE_EVENTS: PermissionState.GRANTED}),
        applications=ledger,
    )

    assert guarded.decide(spec(), "Music").assurance is Assurance.OWNER

    ledger.verified("Music")

    assert guarded.decide(spec(), "Music").decision is PolicyDecision.ALLOW


def test_the_window_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    # A window, not a session: it does not renew on use, so a long afternoon
    # is a fresh prompt every five minutes rather than one at the start.
    ledger = ApplicationLedger({"music": AccessLevel.VERIFY})
    ledger.verified("Music", at=datetime.now() - VERIFIED_FOR - timedelta(seconds=1))

    assert not ledger.recently_verified("Music")


def test_a_window_covers_one_application_only() -> None:
    ledger = ApplicationLedger(
        {"music": AccessLevel.VERIFY, "mail": AccessLevel.VERIFY}
    )
    ledger.verified("Music")

    assert ledger.recently_verified("Music")
    assert not ledger.recently_verified("Mail")


def test_the_strongest_level_is_asked_every_time() -> None:
    """What needs both factors is what cannot be undone.

    "I did this five minutes ago" is not a reason to skip asking about
    something irreversible, so the window does not apply.
    """
    ledger = ApplicationLedger({"messages": AccessLevel.OPEN})
    ledger.verified("Messages")
    guarded = PermissionPolicy(PermissionLedger(), applications=ledger)

    verdict = guarded.decide(spec(assurance=Assurance.OWNER_AND_PASSWORD), "Messages")

    assert verdict.assurance is Assurance.OWNER_AND_PASSWORD


def test_changing_a_level_closes_any_window_under_the_old_one() -> None:
    ledger = ApplicationLedger({"music": AccessLevel.VERIFY})
    ledger.verified("Music")

    ledger.remember("Music", AccessLevel.VERIFY)

    assert not ledger.recently_verified("Music")
