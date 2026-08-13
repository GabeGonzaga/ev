from __future__ import annotations

from pathlib import Path

import pytest

from ev.application.applications import ApplicationLedger
from ev.application.policy import PermissionLedger, PermissionPolicy
from ev.application.speech import Speaker
from ev.capabilities.applications.adapters import QUIT, ApplicationAdapter
from ev.capabilities.applications.args import ApplicationArgs
from ev.capabilities.applications.service import OPEN, ApplicationService
from ev.capabilities.applications.tools import application_tools
from ev.domain.access import AccessLevel
from ev.domain.permissions import Permission, PermissionState
from ev.domain.results import ToolErrorCode
from ev.infrastructure.macos.applescript import AppleScriptClient
from ev.infrastructure.macos.applications import Applications
from ev.infrastructure.macos.processes import ProcessRunner
from ev.registry import CallRecord, Registry
from tests.conftest import FakeBin


class Installed(Applications):
    """A Mac with four applications on it."""

    def __init__(self, names: list[str] | None = None) -> None:
        self._names = names or [
            "Safari",
            "Spotify",
            "Visual Studio Code",
            "GitHub Desktop",
        ]

    def installed(self) -> list[str]:
        return self._names


class Journal:
    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    async def record(self, record: CallRecord) -> None:
        self.records.append(record)


class Allowing:
    async def confirm(self, request: object) -> bool:
        return True


def service(applications: Applications | None = None) -> ApplicationService:
    return ApplicationService(
        ApplicationAdapter(ProcessRunner(), AppleScriptClient(ProcessRunner())),
        applications or Installed(),
        Speaker("en"),
    )


# --- the name is resolved, never obeyed ------------------------------------


@pytest.mark.asyncio
async def test_a_spoken_name_is_matched_against_what_is_installed(
    fake_bin: FakeBin,
) -> None:
    # "visual studio code" is how it is dictated; `Visual Studio Code` is what
    # is on the disk, and `open -a` given the first would launch nothing.
    result = await service().open(ApplicationArgs(name="visual studio code"))

    assert result.ok
    assert fake_bin.argv() == ["-a", "Visual Studio Code"]


@pytest.mark.asyncio
async def test_an_application_that_is_not_here_is_refused(fake_bin: FakeBin) -> None:
    """Nothing rather than a guess.

    Launching the wrong application is a visible and occasionally alarming
    thing to do on someone's behalf.
    """
    result = await service().open(ApplicationArgs(name="Photoshop"))

    assert not result.ok
    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert "Photoshop" in result.error.message
    assert not fake_bin.was_run()


@pytest.mark.asyncio
async def test_an_ambiguous_name_is_refused_rather_than_picked(
    fake_bin: FakeBin,
) -> None:
    result = await service(Installed(["Mail", "Mailspring"])).open(
        ApplicationArgs(name="mail")
    )

    # `Mail` is an exact match and wins; the ambiguity is between the two only
    # for something that matches neither exactly.
    assert result.ok
    assert fake_bin.argv() == ["-a", "Mail"]


@pytest.mark.asyncio
async def test_quitting_goes_through_the_dictionary_not_a_kill(
    fake_bin: FakeBin,
) -> None:
    """`CLAUDE.md`'s order of preference: the scripting dictionary first.

    `quit` lets the application put its own documents away. Killing it does
    not, and the difference is somebody's unsaved work.
    """
    await service().quit(ApplicationArgs(name="Spotify"))

    assert fake_bin.argv() == ["-e", QUIT, "--", "Spotify"]


def test_the_name_reaches_applescript_as_a_value(fake_bin: FakeBin) -> None:
    # `tell application theName`, never `tell application "…"` built by
    # interpolation. This is invariant 2 for a name the model supplied.
    assert "theName" in QUIT
    assert 'tell application "' not in QUIT


# --- how the level applies -------------------------------------------------


def door(levels: dict[str, AccessLevel]) -> tuple[Registry, Journal]:
    journal = Journal()
    registry = Registry(
        policy=PermissionPolicy(
            PermissionLedger({Permission.APPLE_EVENTS: PermissionState.GRANTED}),
            applications=ApplicationLedger(levels),
        ),
        confirmation=Allowing(),
        journal=journal,
    )
    for spec in application_tools(service(), Installed()):
        registry.register(spec)
    return registry, journal


@pytest.mark.asyncio
async def test_the_level_is_read_for_the_application_that_was_meant(
    fake_bin: FakeBin,
) -> None:
    """`safari` blocked must block `Safari`, and a spoken `safari` too.

    The level is looked up with the resolved name, from validated arguments,
    so what is checked is what would actually be launched.
    """
    registry, _ = door({"safari": AccessLevel.BLOCKED})

    result = await registry.call(OPEN, {"name": "safari"})

    assert not result.ok
    assert result.error is not None
    assert "blocked" in result.error.message
    assert not fake_bin.was_run()


@pytest.mark.asyncio
async def test_an_application_that_does_not_exist_is_still_gated(
    fake_bin: FakeBin,
) -> None:
    # It resolves to nothing, so the spoken name is what the policy sees. An
    # unknown application is `ask`, and a surface that says yes lets it reach
    # the service -- which is where it is told there is no such application.
    registry, journal = door({})

    result = await registry.call(OPEN, {"name": "Photoshop"})

    assert not result.ok
    assert journal.records[0].result.ok is False


def test_opening_declares_no_permission_and_quitting_declares_apple_events() -> None:
    opening, quitting = application_tools(service(), Installed())

    assert opening.permissions == frozenset()
    assert quitting.permissions == frozenset({Permission.APPLE_EVENTS})


# --- what is installed -----------------------------------------------------


def test_the_list_comes_from_the_folders_macos_uses(tmp_path: Path) -> None:
    (tmp_path / "Safari.app").mkdir()
    (tmp_path / "Notes.app").mkdir()
    (tmp_path / "not-an-app").mkdir()

    assert Applications((tmp_path,)).installed() == ["Notes", "Safari"]


def test_a_folder_that_cannot_be_read_is_not_an_error(tmp_path: Path) -> None:
    # One place out of five with nothing to contribute, which is what a Mac
    # without ~/Applications looks like.
    assert Applications((tmp_path / "nowhere",)).installed() == []
