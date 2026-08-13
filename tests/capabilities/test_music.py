from __future__ import annotations

import pytest
from pydantic import ValidationError

from ev.application.applications import ApplicationLedger
from ev.application.policy import PermissionLedger, PermissionPolicy
from ev.application.speech import Speaker
from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.args import ControlArgs, PlayArgs, VolumeArgs
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

    def __init__(
        self,
        playlists: list[str],
        albums: list[str] | None = None,
        artists: list[str] | None = None,
    ) -> None:
        self.names = playlists
        self.album_names = albums or []
        self.artist_names = artists or []
        self.played: list[str] = []

    async def playlists(self) -> list[str]:
        return self.names

    async def albums(self) -> list[str]:
        return self.album_names

    async def artists(self) -> list[str]:
        return self.artist_names

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
