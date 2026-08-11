from __future__ import annotations

import pytest
from pydantic import ValidationError

from ev.application.policy import PermissionLedger, PermissionPolicy
from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.args import PlayArgs
from ev.capabilities.music.service import MusicService
from ev.capabilities.music.tools import music_tools
from ev.domain.permissions import Permission, PermissionState
from ev.domain.results import ToolErrorCode
from ev.domain.risk import RiskLevel
from ev.infrastructure.macos.applescript import AppleScriptClient
from ev.infrastructure.macos.processes import ProcessRunner
from ev.registry import CallRecord, Registry
from tests.conftest import FakeBin

# Written out rather than imported: the point of the assertion is that this
# exact text is what reaches osascript, so importing the constant would only
# assert that a variable equals itself.
EXPECTED_SOURCE = """on run argv
\tset theName to item 1 of argv
\tset theKind to item 2 of argv
\ttell application "Music"
\t\tif theKind is "playlist" then
\t\t\tif not (exists playlist theName) then
\t\t\t\terror "there is no playlist called " & theName
\t\t\tend if
\t\t\tplay playlist theName
\t\telse
\t\t\tset lib to library playlist 1
\t\t\tif theKind is "album" then
\t\t\t\tset matches to (every track of lib whose album is theName)
\t\t\telse
\t\t\t\tset matches to (every track of lib whose name is theName)
\t\t\tend if
\t\t\tif matches is {} then
\t\t\t\terror "nothing in the library matches " & theName
\t\t\tend if
\t\t\tset startAt to item 1 of matches
\t\t\tif theKind is "album" then
\t\t\t\trepeat with aTrack in matches
\t\t\t\t\tif track number of aTrack is 1 then
\t\t\t\t\t\tset startAt to contents of aTrack
\t\t\t\t\t\texit repeat
\t\t\t\t\tend if
\t\t\t\tend repeat
\t\t\tend if
\t\t\tplay startAt
\t\tend if
\t\treturn name of current track
\tend tell
end run"""


class CollectingJournal:
    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    async def record(self, record: CallRecord) -> None:
        self.records.append(record)


class RefusingConfirmation:
    async def confirm(self, request: object) -> bool:  # pragma: no cover
        raise AssertionError("music.play must not require confirmation")


def build(*, granted: bool) -> tuple[Registry, CollectingJournal]:
    states = (
        {Permission.APPLE_EVENTS: PermissionState.GRANTED}
        if granted
        else {Permission.APPLE_EVENTS: PermissionState.UNDETERMINED}
    )
    service = MusicService(MusicAdapter(AppleScriptClient(ProcessRunner())))
    journal = CollectingJournal()
    registry = Registry(
        policy=PermissionPolicy(PermissionLedger(states)),
        confirmation=RefusingConfirmation(),
        journal=journal,
    )
    for spec in music_tools(service):
        registry.register(spec)
    return registry, journal


# --- arguments ------------------------------------------------------------


def test_kind_is_required_because_play_x_is_ambiguous() -> None:
    with pytest.raises(ValidationError):
        PlayArgs.model_validate({"name": "Blonde"})


def test_kind_is_a_closed_set() -> None:
    with pytest.raises(ValidationError):
        PlayArgs.model_validate({"name": "Blonde", "kind": "record"})


def test_an_empty_name_is_refused() -> None:
    with pytest.raises(ValidationError):
        PlayArgs.model_validate({"name": "", "kind": "album"})


# --- the adapter boundary -------------------------------------------------


@pytest.mark.asyncio
async def test_the_exact_source_and_argv_reach_osascript(fake_bin: FakeBin) -> None:
    adapter = MusicAdapter(AppleScriptClient(ProcessRunner()))

    await adapter.play("Blonde", "album")

    assert fake_bin.command() == "osascript"
    assert fake_bin.argv() == ["-e", EXPECTED_SOURCE, "--", "Blonde", "album"]


@pytest.mark.asyncio
async def test_a_hostile_name_stays_an_argument(fake_bin: FakeBin) -> None:
    # The reason values travel as argv: interpolated into the source, this
    # would close the string and continue as code.
    hostile = '" & do shell script "rm -rf ~" & "'
    adapter = MusicAdapter(AppleScriptClient(ProcessRunner()))

    await adapter.play(hostile, "album")

    argv = fake_bin.argv()
    assert argv[1] == EXPECTED_SOURCE
    assert argv[3] == hostile
    assert "do shell script" not in argv[1]


@pytest.mark.asyncio
async def test_the_scripts_own_error_is_what_the_user_hears(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_EXIT", "1")
    monkeypatch.setenv(
        "EV_FAKE_STDERR",
        "execution error: nothing in the library matches Blonde (-2700)",
    )
    registry, _ = build(granted=True)

    result = await registry.call("music.play", {"name": "Blonde", "kind": "album"})

    assert result.error is not None
    assert result.error.code is ToolErrorCode.ADAPTER_FAILED
    assert result.error.message == "nothing in the library matches Blonde"


# --- the whole chain ------------------------------------------------------


@pytest.mark.asyncio
async def test_the_permission_gate_stops_it_before_macos_is_asked(
    fake_bin: FakeBin,
) -> None:
    registry, journal = build(granted=False)

    result = await registry.call("music.play", {"name": "Blonde", "kind": "album"})

    assert result.error is not None
    assert result.error.code is ToolErrorCode.PERMISSION_DENIED
    assert "apple_events" in result.error.message
    assert not fake_bin.was_run()
    assert journal.records[0].result.ok is False


@pytest.mark.asyncio
async def test_an_asserted_permission_lets_the_call_through(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_STDOUT", "Nikes")
    registry, journal = build(granted=True)

    result = await registry.call("music.play", {"name": "Blonde", "kind": "album"})

    assert result.ok
    assert fake_bin.command() == "osascript"
    assert journal.records[0].risk is RiskLevel.SENSITIVE


@pytest.mark.asyncio
async def test_the_speech_reports_the_track_it_actually_started_on(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    # play takes one item, so an album starts somewhere. Saying only "Playing
    # Blonde" would claim more than this capability does.
    monkeypatch.setenv("EV_FAKE_STDOUT", "Nikes")
    registry, journal = build(granted=True)

    result = await registry.call("music.play", {"name": "Blonde", "kind": "album"})

    assert result.speech == "Playing Blonde, from Nikes"
    assert result.data["started_at"] == "Nikes"
    assert journal.records[0].result.data["started_at"] == "Nikes"


@pytest.mark.asyncio
async def test_a_playlist_is_named_plainly(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_STDOUT", "Nikes")
    registry, _ = build(granted=True)

    result = await registry.call("music.play", {"name": "Focus", "kind": "playlist"})

    assert result.speech == "Playing Focus"


# --- declaration ----------------------------------------------------------


def test_the_tool_declares_apple_events_and_is_sensitive() -> None:
    service = MusicService(MusicAdapter(AppleScriptClient(ProcessRunner())))

    (spec,) = music_tools(service)

    assert spec.permissions == frozenset({Permission.APPLE_EVENTS})
    assert spec.risk is RiskLevel.SENSITIVE
