from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from ev.application.applications import ApplicationLedger
from ev.application.policy import PermissionLedger, PermissionPolicy
from ev.application.speech import Speaker
from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.args import (
    ControlArgs,
    ModeArgs,
    NowPlayingArgs,
    PlayArgs,
    VolumeArgs,
)
from ev.capabilities.music.service import MusicService
from ev.capabilities.music.tools import music_tools
from ev.domain.access import AccessLevel
from ev.domain.naming import closest
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
\t\treturn my nowPlaying()
\tend tell
end run

on nowPlaying()
\ttell application "Music"
\t\ttry
\t\t\tif player state is stopped then return ""
\t\t\treturn name of current track
\t\ton error
\t\t\treturn ""
\t\tend try
\tend tell
end nowPlaying"""


class CollectingJournal:
    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    async def record(self, record: CallRecord) -> None:
        self.records.append(record)


class RefusingConfirmation:
    async def confirm(self, request: object) -> bool:  # pragma: no cover
        raise AssertionError("music.play must not require confirmation")


def build(
    *, granted: bool, state: PermissionState | None = None
) -> tuple[Registry, CollectingJournal]:
    states = {
        Permission.APPLE_EVENTS: state
        or (PermissionState.GRANTED if granted else PermissionState.UNDETERMINED)
    }
    service = MusicService(MusicAdapter(AppleScriptClient(ProcessRunner())))
    journal = CollectingJournal()
    registry = Registry(
        # Music at `open`: these tests are about what music does, not about
        # whether the user has let E.V. near it. The access levels have their
        # own tests.
        policy=PermissionPolicy(
            PermissionLedger(states),
            applications=ApplicationLedger(default=AccessLevel.OPEN),
        ),
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


EXPECTED_MODE_SOURCE = """on run argv
\tset theSetting to item 1 of argv
\tset theState to item 2 of argv
\ttell application "Music"
\t\tif theSetting is "shuffle" then
\t\t\tset wanted to (theState is "on")
\t\t\tif theState is "toggle" then set wanted to not (shuffle enabled)
\t\t\tset shuffle enabled to wanted
\t\t\tif wanted then return "on"
\t\t\treturn "off"
\t\telse if theSetting is "repeat" then
\t\t\tset wanted to theState
\t\t\tif wanted is "toggle" then
\t\t\t\tif song repeat is off then
\t\t\t\t\tset wanted to "all"
\t\t\t\telse
\t\t\t\t\tset wanted to "off"
\t\t\t\tend if
\t\t\telse if wanted is "on" then
\t\t\t\tset wanted to "all"
\t\t\tend if
\t\t\tif wanted is "one" then
\t\t\t\tset song repeat to one
\t\t\telse if wanted is "all" then
\t\t\t\tset song repeat to all
\t\t\telse
\t\t\t\tset song repeat to off
\t\t\tend if
\t\t\treturn wanted
\t\tend if
\t\treturn ""
\tend tell
end run"""
"""The switch script, as it reaches osascript.

It answers with what it *set*, never with a read-back. `set shuffle enabled to
true` followed by `shuffle enabled` answers false; put a `delay 0.4` between
them and it answers true -- the write lands, the read races it. Measured on
Music 1.6.5, macOS 26.5.2. Reading *before* writing is fine, which is what
makes `toggle` honest: the state being flipped is Music's, not one E.V.
remembered.

An unrecognised setting falls through to `return ""` without writing
anything, which is the path `make applescript` runs."""


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
async def test_a_refused_permission_stops_it_before_macos_is_asked_again(
    fake_bin: FakeBin,
) -> None:
    """Refused, not undecided.

    macOS raises no second dialog for something it has already refused, so
    trying again is a silent failure with extra steps. The useful answer is
    where the decision is changed.
    """
    registry, journal = build(granted=False, state=PermissionState.DENIED)

    result = await registry.call("music.play", {"name": "Blonde", "kind": "album"})

    assert result.error is not None
    assert result.error.code is ToolErrorCode.PERMISSION_DENIED
    assert "apple_events" in result.error.message
    assert "System Settings" in result.error.message
    assert not fake_bin.was_run()
    assert journal.records[0].result.ok is False


@pytest.mark.asyncio
async def test_an_undecided_permission_lets_macos_do_the_asking(
    fake_bin: FakeBin,
) -> None:
    # The whole change: E.V. used to refuse here, and the person had to type
    # --grant to get out of its way. Now the call reaches osascript, which is
    # the only thing that can make macOS put a dialog on screen.
    registry, _ = build(granted=False)

    await registry.call("music.play", {"name": "Blonde", "kind": "album"})

    assert fake_bin.was_run()


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
async def test_the_speech_says_what_was_asked_for_not_what_music_answers(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    # play takes one item, so an album starts somewhere. Saying only "Playing
    # Blonde" would claim more than this capability does.
    monkeypatch.setenv("EV_FAKE_STDOUT", "Nikes")
    registry, journal = build(granted=True)

    result = await registry.call("music.play", {"name": "Blonde", "kind": "album"})

    # `play` returns before the player has moved, so `name of current track`
    # is often the song that was playing a moment ago. Announcing that as the
    # new one is a lie that sounds like a broken library -- measured against a
    # real one: asking for "mona lisa" said "A tocar wacced out murals".
    assert result.speech == "Playing Blonde"
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
    # One at a time, not `duplicate matches to theQueue`: Music answers
    # "Can't set user playlist ... to {shared track id ...}" when the list is
    # long, which is what an artist's 112 tracks look like.
    assert "duplicate aTrack to theQueue" in source
    assert "play theQueue" in source
    # Its own playlist, replaced each time, and never anything else.
    assert fake_bin.argv()[3:] == ["Blonde", "E.V. queue", "500"]


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


# --- what is playing ------------------------------------------------------


@pytest.mark.asyncio
async def test_the_cover_is_written_where_it_was_told_to(
    fake_bin: FakeBin, tmp_path: Path
) -> None:
    adapter = MusicAdapter(AppleScriptClient(ProcessRunner()))
    where = tmp_path / "artwork.bin"

    await adapter.now_playing(where)

    assert fake_bin.argv()[-1] == str(where)


@pytest.mark.asyncio
async def test_a_short_answer_is_padded_rather_than_indexed_off_the_end(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A script that stopped early must not become an IndexError upstream."""
    monkeypatch.setenv("EV_FAKE_STDOUT", "paused\nAirplane Mode")

    fields = await MusicAdapter(AppleScriptClient(ProcessRunner())).now_playing(None)

    assert len(fields) == 10
    assert fields[0] == "paused"
    assert fields[9] == ""


@pytest.mark.asyncio
async def test_a_song_with_verses_does_not_become_nine_fields_and_a_mess(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lyrics are the one field with newlines of its own, so they come last
    and are not split."""
    monkeypatch.setenv(
        "EV_FAKE_STDOUT",
        "playing\nNikes\nFrank Ocean\nBlonde\n62\n314\non\nall\n/tmp/art\n"
        "first line\nsecond line\n\nafter a blank one",
    )

    fields = await MusicAdapter(AppleScriptClient(ProcessRunner())).now_playing(None)

    assert len(fields) == 10
    assert fields[8] == "/tmp/art"
    assert fields[9] == "first line\nsecond line\n\nafter a blank one"


class Reading:
    """A player that answers a read, and counts how often it was asked."""

    def __init__(self, cover: str) -> None:
        self.asked = 0
        self.cover = cover

    async def now_playing(self, artwork: Path | None) -> list[str]:
        self.asked += 1
        return [
            "playing",
            "Nikes",
            "Frank Ocean",
            "Blonde",
            "62",
            "314",
            "on",
            "all",
            self.cover,
            "  a verse\nand another  ",
        ]


@pytest.mark.asyncio
async def test_what_is_playing_is_reported_for_a_display_to_draw(
    tmp_path: Path,
) -> None:
    cover = tmp_path / "artwork.bin"
    cover.write_bytes(b"\xff\xd8\xff" + b"jpeg bytes")
    service = MusicService(cast(MusicAdapter, Reading(str(cover))))

    result = await service.now_playing(NowPlayingArgs())

    assert result.ok
    # Nothing is said out loud: a status line spoken every second is not an
    # assistant.
    assert result.speech is None
    assert result.data["track"] == "Nikes"
    assert result.data["artist"] == "Frank Ocean"
    assert result.data["at"] == 62
    assert result.data["length"] == 314
    assert result.data["shuffle"] is True
    assert result.data["repeat"] == "all"
    assert str(result.data["cover"]).startswith("data:image/jpeg;base64,")
    # Trimmed at the ends and untouched in the middle: a blank line inside a
    # song is the song's.
    assert result.data["lyrics"] == "a verse\nand another"


@pytest.mark.asyncio
async def test_the_cover_is_read_once_per_record(tmp_path: Path) -> None:
    """Artwork is a few hundred kilobytes and the display asks every second."""
    cover = tmp_path / "artwork.bin"
    cover.write_bytes(b"\x89PNG" + b"png bytes")
    service = MusicService(cast(MusicAdapter, Reading(str(cover))))

    first = await service.now_playing(NowPlayingArgs())
    cover.unlink()  # gone: a second read of the file would fail
    again = await service.now_playing(NowPlayingArgs())

    assert again.data["cover"] == first.data["cover"]
    assert str(first.data["cover"]).startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_something_that_is_not_an_image_is_not_offered_as_one(
    tmp_path: Path,
) -> None:
    cover = tmp_path / "artwork.bin"
    cover.write_bytes(b"not an image at all")
    service = MusicService(cast(MusicAdapter, Reading(str(cover))))

    result = await service.now_playing(NowPlayingArgs())

    assert result.data["cover"] is None


def test_reading_the_player_is_not_written_to_the_journal() -> None:
    """ADR 0038. Everything else about the call is unchanged."""
    service = MusicService(MusicAdapter(AppleScriptClient(ProcessRunner())))
    specs = {spec.name: spec for spec in music_tools(service)}

    reading = specs["music.now_playing"]
    assert reading.journalled is False
    assert reading.risk is RiskLevel.SAFE
    # Still the same door: same permission, same application, same level.
    assert reading.permissions == frozenset({Permission.APPLE_EVENTS})
    assert reading.application is not None

    for name, spec in specs.items():
        if name != "music.now_playing":
            assert spec.journalled is True


# --- shuffle and repeat ---------------------------------------------------


@pytest.mark.asyncio
async def test_each_switch_reaches_music_as_a_setting_and_a_state(
    fake_bin: FakeBin,
) -> None:
    adapter = MusicAdapter(AppleScriptClient(ProcessRunner()))

    for setting, state in (
        ("shuffle", "on"),
        ("shuffle", "off"),
        ("shuffle", "toggle"),
        ("repeat", "all"),
        ("repeat", "one"),
        ("repeat", "toggle"),
    ):
        await adapter.mode(setting, state)
        assert fake_bin.argv()[-2:] == [setting, state]


@pytest.mark.asyncio
async def test_the_switch_script_is_exactly_this(fake_bin: FakeBin) -> None:
    adapter = MusicAdapter(AppleScriptClient(ProcessRunner()))

    await adapter.mode("repeat", "toggle")

    assert fake_bin.argv()[1] == EXPECTED_MODE_SOURCE


def test_shuffling_one_track_is_not_a_thing() -> None:
    with pytest.raises(ValidationError):
        ModeArgs(setting="shuffle", state="one")


def test_a_switch_left_alone_flips() -> None:
    """Saying "shuffle" is pressing the button, which is the default."""
    assert ModeArgs(setting="shuffle").state == "toggle"
    assert ModeArgs(setting="repeat").state == "toggle"


@pytest.mark.asyncio
async def test_the_answer_says_which_way_the_switch_went() -> None:
    class Switched:
        def __init__(self, answer: str) -> None:
            self.answer = answer

        async def mode(self, setting: str, state: str) -> str:
            return self.answer

    for answer, expected in (
        ("on", "Shuffle on"),
        ("off", "Shuffle off"),
    ):
        service = MusicService(cast(MusicAdapter, Switched(answer)))
        result = await service.mode(ModeArgs(setting="shuffle"))

        assert result.ok
        assert result.data == {"setting": "shuffle", "state": answer}
        assert result.speech == expected

    service = MusicService(cast(MusicAdapter, Switched("one")))
    result = await service.mode(ModeArgs(setting="repeat", state="one"))

    assert result.speech == "Repeating this track"


@pytest.mark.asyncio
async def test_a_position_music_does_not_have_is_reported_not_spoken() -> None:
    class Confused:
        async def mode(self, setting: str, state: str) -> str:
            return ""

    service = MusicService(cast(MusicAdapter, Confused()))
    result = await service.mode(ModeArgs(setting="repeat"))

    assert not result.ok
    assert result.error is not None
    assert result.error.code is ToolErrorCode.ADAPTER_FAILED


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

    assert set(specs) == {
        "music.play",
        "music.control",
        "music.mode",
        "music.now_playing",
        "music.volume",
    }
    for name, spec in specs.items():
        assert spec.permissions == frozenset({Permission.APPLE_EVENTS})
        # Reading what is playing changes nothing, so it is safe -- and it is
        # gated by the application's level rather than by its risk.
        reads = name == "music.now_playing"
        assert spec.risk is (RiskLevel.SAFE if reads else RiskLevel.SENSITIVE)


# --- the name that was not an album ---------------------------------------


class Library:
    """A library where `Indie kid??` is a playlist and no album by that name
    exists, which is the library that produced the bug."""

    def __init__(
        self,
        playlists: list[str],
        albums: list[str] | None = None,
        artists: list[str] | None = None,
        tracks: list[str] | None = None,
    ) -> None:
        self.names = playlists
        self.album_names = albums or []
        self.artist_names = artists or []
        self.track_names = tracks or []
        self.played: list[str] = []

    async def playlists(self) -> list[str]:
        return self.names

    async def albums(self) -> list[str]:
        return self.album_names

    async def artists(self) -> list[str]:
        return self.artist_names

    async def tracks(self) -> list[str]:
        return self.track_names

    async def play_artist(self, name: str) -> str:
        self.played.append(name)
        return "Some Track"

    async def play_album(self, name: str) -> str:
        # Exactly what Music does: an album plays if the library has one
        # spelled that way, and nothing else counts.
        if name not in self.album_names:
            raise AppleScriptError(f"nothing in the library matches {name}")
        self.played.append(name)
        return "Some Track"

    async def play_track(self, name: str) -> str:
        # As Music does: a song plays if the library has one spelled that way.
        if name not in self.track_names:
            raise AppleScriptError(f"nothing in the library matches {name}")
        self.played.append(name)
        return "Some Track"

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
    assert result.speech == "Nothing called Indie Kid. Playing the playlist Indie kid??"
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
    # The library's own wording is no longer repeated back: it named a
    # spelling nobody used. What is said instead is what E.V. does know --
    # that nothing matched, and what the playlists are called.
    assert "Nothing in the library matches" in result.error.message
    assert "Music That Does Not Exist" in result.error.message
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


# --- volume, relative and absolute ----------------------------------------


def test_a_volume_is_a_level_or_a_change_and_not_both() -> None:
    # "Set it to 40 and also turn it up" is not a request, and a model sending
    # both should be corrected rather than obeyed in some order.
    with pytest.raises(ValidationError):
        VolumeArgs.model_validate({"level": 40, "change": "up"})

    with pytest.raises(ValidationError):
        VolumeArgs.model_validate({})


@pytest.mark.asyncio
async def test_louder_steps_rather_than_setting(fake_bin: FakeBin) -> None:
    # Reading the volume and then writing it back would race with whoever is
    # holding the volume key. Music does the arithmetic and the clamping.
    await MusicAdapter(AppleScriptClient(ProcessRunner())).step(10)

    source = fake_bin.argv()[1]
    assert "(sound volume) + theStep" in source
    assert "if wanted > 100 then set wanted to 100" in source
    assert fake_bin.argv()[-1] == "10"


@pytest.mark.asyncio
async def test_mute_uses_musics_own_mute(fake_bin: FakeBin) -> None:
    # Not "volume 0": unmuting should restore the level the person chose, not
    # a number E.V. invented.
    await MusicAdapter(AppleScriptClient(ProcessRunner())).mute(True)

    assert "set mute to" in fake_bin.argv()[1]
    assert fake_bin.argv()[-1] == "true"


@pytest.mark.asyncio
async def test_the_spoken_answer_names_the_new_volume(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_STDOUT", "60")
    registry, _ = build(granted=True)

    result = await registry.call("music.volume", {"change": "up"})

    assert result.speech == "Volume 60"


@pytest.mark.asyncio
async def test_muting_says_so_rather_than_naming_a_number(
    fake_bin: FakeBin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EV_FAKE_STDOUT", "60")
    registry, _ = build(granted=True)

    result = await registry.call("music.volume", {"change": "mute"})

    assert result.speech == "Muted"


# --- what the controls say ------------------------------------------------


class Playing:
    """A player that answers with whatever it is on now."""

    def __init__(self, track: str) -> None:
        self._track = track

    async def control(self, action: str) -> str:
        return self._track


@pytest.mark.asyncio
async def test_a_control_speaks_words_not_a_phrase_key() -> None:
    # This shipped saying "music.paused" out loud: the lookup table held keys
    # and the key went straight into `speech`.
    service = MusicService(Playing("Nikes"), Speaker("en"))  # type: ignore[arg-type]

    result = await service.control(ControlArgs(action="pause"))

    assert result.speech == "Paused"


@pytest.mark.asyncio
async def test_skipping_names_the_new_track() -> None:
    service = MusicService(Playing("Solo"), Speaker("en"))  # type: ignore[arg-type]

    result = await service.control(ControlArgs(action="next"))

    assert result.speech == "Skipped to Solo"


@pytest.mark.asyncio
async def test_the_preposition_is_translated_not_concatenated() -> None:
    # "Saltei" + " to " + track is what concatenation gives. The whole line is
    # a phrase per language for exactly this reason.
    service = MusicService(Playing("Solo"), Speaker("pt-PT"))  # type: ignore[arg-type]

    result = await service.control(ControlArgs(action="next"))

    assert result.speech == "Saltei para Solo"


@pytest.mark.asyncio
async def test_a_stopped_player_is_not_asked_what_is_playing() -> None:
    service = MusicService(Playing(""), Speaker("en"))  # type: ignore[arg-type]

    result = await service.control(ControlArgs(action="stop"))

    assert result.speech == "Stopped"


def test_the_control_script_survives_a_player_with_no_track() -> None:
    """A real line from the journal: "Music got an error: Can't get name of
    current track".

    Skipping past the end of a queue leaves a player that is not stopped and
    has no current track. The action worked; only the answer was missing, and
    it turned a successful pause into a failed turn.
    """
    from ev.capabilities.music.adapters import CONTROL

    assert "on error" in CONTROL
    # `my`, not bare: a handler called inside a `tell application` block is
    # sent to the application, which answers "Can't continue nowPlaying".
    # It compiled, it shipped, and `make applescript` is what found it.
    assert "my nowPlaying()" in CONTROL


# --- what a library actually contains --------------------------------------


@pytest.mark.asyncio
async def test_an_artist_plays_everything_they_are_on() -> None:
    """Resolved before it is played, and matched with `contains` after.

    Half of what an artist recorded is credited to a collaboration, and
    `artist is "Kendrick Lamar"` finds none of it.
    """
    library = Library([], artists=["Kendrick Lamar", "Kendrick Lamar & SZA"])
    service = MusicService(library, Speaker("en"))  # type: ignore[arg-type]

    result = await service.play(PlayArgs(name="kendrick", kind="artist"))

    assert result.ok
    assert library.played == ["Kendrick Lamar"]


@pytest.mark.asyncio
async def test_an_album_the_library_spells_differently_still_plays() -> None:
    # The real case: asking for `21st Century Breakdown` misses, because the
    # library calls it `21st Century Breakdown (Deluxe Edition)`.
    library = Library([], albums=["21st Century Breakdown (Deluxe Edition)"])
    service = MusicService(library, Speaker("en"))  # type: ignore[arg-type]

    result = await service.play(PlayArgs(name="21st Century Breakdown", kind="album"))

    assert result.ok
    assert library.played == ["21st Century Breakdown (Deluxe Edition)"]
    assert result.speech is not None
    assert "Deluxe" in result.speech


@pytest.mark.asyncio
async def test_a_name_asked_for_as_an_album_is_looked_for_as_an_artist() -> None:
    # "Play the album Kendrick" is a reasonable thing to say and a wrong kind.
    # Being wrong about the kind should not be fatal.
    library = Library([], artists=["Kendrick Lamar"])
    service = MusicService(library, Speaker("en"))  # type: ignore[arg-type]

    result = await service.play(PlayArgs(name="kendrick", kind="album"))

    assert result.ok
    assert result.data["kind"] == "artist"
    assert library.played == ["Kendrick Lamar"]


@pytest.mark.asyncio
async def test_albums_come_before_artists_and_playlists() -> None:
    # One name, three possible meanings. Albums first: it is the most specific
    # thing the word can name.
    library = Library(["Nikes"], albums=["Nikes"], artists=["Nikes"])
    service = MusicService(library, Speaker("en"))  # type: ignore[arg-type]

    result = await service.play(PlayArgs(name="nikes", kind="album"))

    assert result.data["kind"] == "album"


def test_an_artist_is_matched_with_contains_not_is() -> None:
    from ev.capabilities.music.adapters import PLAY_ARTIST

    assert "artist contains theName" in PLAY_ARTIST


# --- songs, and the versions a library keeps of them ----------------------


@pytest.mark.asyncio
async def test_a_song_the_library_spells_differently_still_plays() -> None:
    # 746 of the 3975 track names in the library this was written against
    # carry a suffix nobody says out loud.
    library = Library([], tracks=["Stick Season (Live From Fenway Park)"])
    service = MusicService(library, Speaker("en"))  # type: ignore[arg-type]

    result = await service.play(PlayArgs(name="Stick Season", kind="track"))

    assert result.ok
    assert result.data["kind"] == "track"


def test_editions_of_one_song_are_one_song() -> None:
    """Three recordings of `Here Comes the Sun`, and any of them answers.

    The prefix rule alone refused these: none of the three is the beginning of
    the others, so they looked like different things.
    """
    editions = [
        "Here Comes the Sun (2019 Mix)",
        "Here Comes the Sun (feat. dodie)",
        "Here Comes The Sun (Take 9)",
    ]

    assert closest("here comes the sun", editions) == "Here Comes the Sun (2019 Mix)"


def test_an_outtake_is_not_what_anyone_meant() -> None:
    # Sorting by length picked `(Take 9)` over `(2019 Mix)`, because it is
    # shorter. A take is a different recording, not a different master.
    assert (
        closest("let it be", ["Let It Be (Take 28)", "Let It Be (2021 Mix)"])
        == "Let It Be (2021 Mix)"
    )


def test_different_songs_that_start_alike_stay_ambiguous() -> None:
    """`Something` is a Beatles song and the start of two others.

    An edition qualifies what came before it -- a parenthesis, a dash. An
    ordinary word after it means a different song, and picking one of those
    would be picking by coin toss.
    """
    assert (
        closest(
            "something",
            ["Something (2019 Mix)", "Something About Us", "something bout tomorrow"],
        )
        is None
    )


@pytest.mark.asyncio
async def test_the_kind_asked_for_is_looked_at_first() -> None:
    # One word, and the library has it as both. Asked for a song, the song is
    # what plays.
    library = Library([], albums=["Clancy"], tracks=["Clancy"])
    service = MusicService(library, Speaker("en"))  # type: ignore[arg-type]

    result = await service.play(PlayArgs(name="clancy", kind="track"))

    assert result.data["kind"] == "track"
