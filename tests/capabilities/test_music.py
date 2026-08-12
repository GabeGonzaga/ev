from __future__ import annotations

import pytest
from pydantic import ValidationError

from ev.application.policy import PermissionLedger, PermissionPolicy
from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.args import ControlArgs, PlayArgs, VolumeArgs
from ev.capabilities.music.service import MusicService, closest
from ev.capabilities.music.tools import music_tools
from ev.domain.permissions import Permission, PermissionState
from ev.domain.results import ToolErrorCode
from ev.domain.risk import RiskLevel
from ev.infrastructure.macos.applescript import AppleScriptClient, AppleScriptError
from ev.infrastructure.macos.processes import ProcessRunner
from ev.registry import CallRecord, Registry
from tests.conftest import FakeBin

# Written out rather than imported: the point of the assertion is that this
# exact text is what reaches osascript, so importing the constant would only
# assert that a variable equals itself.
EXPECTED_TRACK_SOURCE = """on run argv
\tset theName to item 1 of argv
\ttell application "Music"
\t\tset lib to library playlist 1
\t\tset matches to (every track of lib whose name is theName)
\t\tif matches is {} then
\t\t\terror "nothing in the library matches " & theName
\t\tend if
\t\tplay item 1 of matches
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

    await adapter.play_track("Nikes")

    assert fake_bin.command() == "osascript"
    assert fake_bin.argv() == ["-e", EXPECTED_TRACK_SOURCE, "--", "Nikes"]


@pytest.mark.asyncio
async def test_a_hostile_name_stays_an_argument(fake_bin: FakeBin) -> None:
    # The reason values travel as argv: interpolated into the source, this
    # would close the string and continue as code.
    hostile = '" & do shell script "rm -rf ~" & "'
    adapter = MusicAdapter(AppleScriptClient(ProcessRunner()))

    await adapter.play_track(hostile)

    argv = fake_bin.argv()
    assert argv[1] == EXPECTED_TRACK_SOURCE
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
    # The fake answers every osascript the same way, which is enough here: the
    # listing returns "Focus", so "Focus" is what resolves and what plays.
    monkeypatch.setenv("EV_FAKE_STDOUT", "Focus")
    registry, _ = build(granted=True)

    result = await registry.call("music.play", {"name": "Focus", "kind": "playlist"})

    assert result.speech == "Playing Focus"


# --- declaration ----------------------------------------------------------


# --- playlists are matched against the ones that exist --------------------


def test_a_spoken_name_finds_a_punctuated_playlist() -> None:
    """Real playlist names from a real library.

    Nobody dictates "GO w/Flow!!" or "{Jazzy}". Matching what was said against
    what exists is the same rule CLAUDE.md states for shortcuts.
    """
    existing = ["{Jazzy}", "GO w/Flow!!", "Indie kid??", "Main PlayList :D", "Logic"]

    assert closest("Jazzy", existing) == "{Jazzy}"
    assert closest("go w flow", existing) == "GO w/Flow!!"
    assert closest("indie kid", existing) == "Indie kid??"
    assert closest("main playlist", existing) == "Main PlayList :D"


def test_an_exact_name_wins_over_a_looser_match() -> None:
    assert closest("Logic", ["Logic", "Logic Pro Favourites"]) == "Logic"


def test_an_ambiguous_name_matches_nothing() -> None:
    # Two plausible playlists is not a reason to pick one. Playing the wrong
    # playlist is worse than saying which ones matched.
    assert closest("jazz", ["Jazz Classics", "Jazz Nights"]) is None


def test_a_name_that_is_only_punctuation_matches_nothing() -> None:
    assert closest("???", ["Indie kid??"]) is None


@pytest.mark.asyncio
async def test_a_playlist_is_resolved_before_it_is_played(fake_bin: FakeBin) -> None:
    adapter = MusicAdapter(AppleScriptClient(ProcessRunner()))
    service = MusicService(adapter)

    async def playlists() -> list[str]:
        return ["{Jazzy}", "GO w/Flow!!"]

    adapter.playlists = playlists  # type: ignore[method-assign]

    result = await service.play(PlayArgs(name="jazzy", kind="playlist"))

    assert result.ok
    # The exact name reaches Music, not the spoken one.
    assert fake_bin.argv()[-1] == "{Jazzy}"
    assert result.data["name"] == "{Jazzy}"


@pytest.mark.asyncio
async def test_an_unknown_playlist_names_the_ones_that_exist(
    fake_bin: FakeBin,
) -> None:
    adapter = MusicAdapter(AppleScriptClient(ProcessRunner()))
    service = MusicService(adapter)

    async def playlists() -> list[str]:
        return ["{Jazzy}", "GROOVY"]

    adapter.playlists = playlists  # type: ignore[method-assign]

    result = await service.play(PlayArgs(name="something else", kind="playlist"))

    assert not result.ok
    assert result.error is not None
    assert "{Jazzy}" in result.error.message


# --- an album plays through -----------------------------------------------


@pytest.mark.asyncio
async def test_an_album_is_played_as_a_playlist(fake_bin: FakeBin) -> None:
    """The fix for what actually happened: it played one song and stopped.

    Music's `play` takes a single item, so playing a track plays a track. A
    playlist is the only thing it will play through, so E.V. keeps one of its
    own and refills it.
    """
    monkeypatched = MusicAdapter(AppleScriptClient(ProcessRunner()))

    await monkeypatched.play_album("Blonde")

    source = fake_bin.argv()[1]
    assert "make new user playlist" in source
    assert "duplicate matches to theQueue" in source
    assert "play theQueue" in source
    # Its own playlist, replaced each time, and never anything else.
    assert fake_bin.argv()[-1] == "E.V. queue"


@pytest.mark.asyncio
async def test_the_queue_is_replaced_not_appended(fake_bin: FakeBin) -> None:
    await MusicAdapter(AppleScriptClient(ProcessRunner())).play_album("Blonde")

    source = fake_bin.argv()[1]
    assert "delete user playlist queueName" in source


# --- the controls ---------------------------------------------------------


@pytest.mark.asyncio
async def test_each_control_reaches_music_as_itself(fake_bin: FakeBin) -> None:
    adapter = MusicAdapter(AppleScriptClient(ProcessRunner()))

    for action in ("pause", "resume", "next", "previous", "stop"):
        await adapter.control(action)
        assert fake_bin.argv()[-1] == action


@pytest.mark.asyncio
async def test_the_volume_is_a_number_music_understands(fake_bin: FakeBin) -> None:
    await MusicAdapter(AppleScriptClient(ProcessRunner())).volume(40)

    assert fake_bin.argv()[-1] == "40"


def test_a_volume_outside_the_dial_is_refused() -> None:
    for bad in (-1, 101):
        with pytest.raises(ValidationError):
            VolumeArgs(level=bad)


def test_an_invented_action_is_refused() -> None:
    with pytest.raises(ValidationError):
        ControlArgs.model_validate({"action": "shuffle everything"})


def test_the_controls_declare_apple_events_too() -> None:
    service = MusicService(MusicAdapter(AppleScriptClient(ProcessRunner())))

    specs = {spec.name: spec for spec in music_tools(service)}

    assert set(specs) == {"music.play", "music.control", "music.volume"}
    for spec in specs.values():
        assert spec.permissions == frozenset({Permission.APPLE_EVENTS})
        assert spec.risk is RiskLevel.SENSITIVE


# --- the name that was not an album ---------------------------------------


class Library:
    """A library where `Indie kid??` is a playlist and no album by that name
    exists, which is the library that produced the bug."""

    def __init__(self, playlists: list[str]) -> None:
        self.names = playlists
        self.played: list[str] = []

    async def playlists(self) -> list[str]:
        return self.names

    async def play_album(self, name: str) -> str:
        raise AppleScriptError(f"nothing in the library matches {name}")

    async def play_track(self, name: str) -> str:
        raise AppleScriptError(f"nothing in the library matches {name}")

    async def play_playlist(self, name: str) -> str:
        self.played.append(name)
        return "Some Track"


@pytest.mark.asyncio
async def test_a_playlist_asked_for_as_an_album_still_plays() -> None:
    """What actually happened: "nothing in the library matches Indie Kid",
    while `Indie kid??` sat in the sidebar.

    No album by that name exists, so there is no second reading to guess
    between. It plays, and says which -- a wrong guess should be audible, not
    silent.
    """
    library = Library(["{Jazzy}", "Indie kid??", "GROOVY"])
    service = MusicService(library)  # type: ignore[arg-type]

    result = await service.play(PlayArgs(name="Indie Kid", kind="album"))

    assert result.ok
    assert library.played == ["Indie kid??"]
    assert (
        result.speech == "No album called Indie Kid. Playing the playlist Indie kid??"
    )
    assert result.data["kind"] == "playlist"
    assert result.data["asked_for"] == "Indie Kid"


@pytest.mark.asyncio
async def test_a_name_that_is_nothing_at_all_still_fails() -> None:
    library = Library(["{Jazzy}"])
    service = MusicService(library)  # type: ignore[arg-type]

    result = await service.play(
        PlayArgs(name="Music That Does Not Exist", kind="album")
    )

    assert not result.ok
    assert result.error is not None
    assert "nothing in the library matches" in result.error.message
    assert library.played == []


@pytest.mark.asyncio
async def test_an_ambiguous_fallback_is_not_taken() -> None:
    # Two plausible playlists is a guess, and a guess plays the wrong music.
    library = Library(["Jazz Classics", "Jazz Nights"])
    service = MusicService(library)  # type: ignore[arg-type]

    result = await service.play(PlayArgs(name="Jazz", kind="album"))

    assert not result.ok
    assert library.played == []


@pytest.mark.asyncio
async def test_a_real_failure_is_not_swallowed_by_the_fallback() -> None:
    class Refused(Library):
        async def play_album(self, name: str) -> str:
            raise AppleScriptError("Not authorized to send Apple events to Music")

    service = MusicService(Refused(["{Jazzy}"]))  # type: ignore[arg-type]

    # A permission problem is not a missing album, and must not be reported as
    # one -- nor turned into playing something else.
    with pytest.raises(AppleScriptError, match="Not authorized"):
        await service.play(PlayArgs(name="Blonde", kind="album"))
