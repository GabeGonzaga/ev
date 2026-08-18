"""Orchestration. Never touches the system directly.

Two things happen here that are not adapter calls, and both are the same idea:
a spoken name is matched against what actually exists rather than passed
through. `CLAUDE.md` states it for shortcuts -- "the name is resolved against
the real list, never passed through freely" -- and a playlist called
`GO w/Flow!!` is why it matters for music too.
"""

from __future__ import annotations

from base64 import b64encode
from collections.abc import Awaitable
from pathlib import Path

from ev.application.speech import Speaker
from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.args import (
    STEP,
    ControlArgs,
    ModeArgs,
    NowPlayingArgs,
    PlayArgs,
    SeekArgs,
    VolumeArgs,
)
from ev.domain.naming import closest
from ev.domain.results import ToolErrorCode, ToolResult
from ev.infrastructure.macos.applescript import AppleScriptError

PLAY = "music.play"
CONTROL = "music.control"
VOLUME = "music.volume"
MODE = "music.mode"
NOW_PLAYING = "music.now_playing"
SEEK = "music.seek"

COVER_TYPES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
}
"""Sniffed from the bytes rather than taken from Music's own answer. The
scripting dictionary reports a format constant that does not always match what
`raw data` actually contains, and a JPEG announced as a PNG renders as
nothing."""


def _clock(seconds: int) -> str:
    """`1:30`. What a person says back about a place in a song."""
    return f"{seconds // 60}:{seconds % 60:02d}"


def _seconds(value: str) -> int:
    """Music answers in whole seconds, or in nothing at all."""
    try:
        return max(0, int(value))
    except ValueError:
        return 0


NOT_FOUND = "nothing in the library matches"
"""What the album and track scripts say when a name is not in the library.
Matched here so a miss can be turned into something useful rather than
repeated back at the user."""

SPOKEN = {
    "pause": "music.paused",
    "resume": "music.resumed",
    "next": "music.next",
    "previous": "music.previous",
    "stop": "music.stopped",
}
"""Action to phrase key. The key is looked up, never spoken: an earlier
version returned it directly and Joana read "music.paused" out loud."""

SWITCHED = {
    ("shuffle", "on"): "music.shuffle_on",
    ("shuffle", "off"): "music.shuffle_off",
    ("repeat", "all"): "music.repeat_all",
    ("repeat", "one"): "music.repeat_one",
    ("repeat", "off"): "music.repeat_off",
}
"""Where each switch ended up, as a phrase key. Where it *ended up*, not what
was asked for: "shuffle" alone is a button press, and the useful half of the
answer is which way it went."""

WITH_TRACK = {"resume", "next", "previous"}
"""The three where naming what is playing now is the useful part of the
answer. Each has its own phrase, because "Skipped" and "Skipped to X" do not
compose by concatenation in every language -- pt-PT wants "para", not "to"."""


class MusicService:
    def __init__(
        self,
        adapter: MusicAdapter,
        speaker: Speaker | None = None,
        artwork: Path | None = None,
    ) -> None:
        self._adapter = adapter
        self._speaker = speaker or Speaker()
        self._artwork = artwork
        self._seen: str | None = None
        self._cover_url: str | None = None

    async def play(self, args: PlayArgs) -> ToolResult:
        if args.kind == "playlist":
            return await self._playlist(args.name)

        if args.kind == "artist":
            # Always resolved: half of what an artist recorded is credited to
            # a collaboration, and `artist is "Kendrick Lamar"` finds none of
            # it. Resolving first is also what turns "kendrick" into a name
            # the library actually uses.
            name = closest(args.name, await self._adapter.artists())
            if name is None:
                return await self._elsewhere(args.name, "artist")
            return await self._started("artist", name, self._adapter.play_artist(name))

        if args.kind == "album":
            try:
                started_at = await self._adapter.play_album(args.name)
            except AppleScriptError as error:
                if NOT_FOUND not in str(error):
                    raise
                return await self._elsewhere(args.name, "album")
            # What is *asked for* is what is said back, never what Music
            # answers with. `play` returns before the player has moved, so
            # `name of current track` is often the track that was playing a
            # moment ago -- and E.V. announcing the previous song as the new
            # one is a lie that sounds like a bug in the library.
            return ToolResult.success(
                PLAY,
                data={"name": args.name, "kind": "album", "started_at": started_at},
                speech=self._speaker.say("music.playing", name=args.name),
            )

        try:
            started_at = await self._adapter.play_track(args.name)
        except AppleScriptError as error:
            if NOT_FOUND not in str(error):
                raise
            # Songs miss for the same reason albums do: the library calls it
            # `Mona Lisa (Apple Music Live)` and nobody says the parenthesis.
            return await self._elsewhere(args.name, "track")

        return ToolResult.success(
            PLAY,
            data={"name": args.name, "kind": "track", "started_at": started_at},
            speech=self._speaker.say("music.playing", name=args.name),
        )

    async def _elsewhere(self, spoken: str, asked_for: str) -> ToolResult:
        """Nothing of that kind by that name. Look for it as the others.

        This is the case that actually happens. "Play the album 21st Century
        Breakdown" misses because the library calls it `21st Century Breakdown
        (Deluxe Edition)`; "play Indie kid" misses because it is a playlist;
        "play Kendrick" misses because it is an artist and half his tracks are
        credited to somebody else as well.

        Albums first, then artists, then playlists -- the order people mean
        them. Whatever is found is said out loud, so a wrong guess is audible
        rather than silent.
        """
        found = await self._find(spoken, asked_for)
        if found is None:
            existing = ", ".join((await self._adapter.playlists())[:5]) or "none"
            return ToolResult.failure(
                PLAY,
                ToolErrorCode.INVALID_ARGUMENTS,
                self._speaker.say(
                    "music.nothing_matches", name=spoken, existing=existing
                ),
            )

        kind, name = found
        playing = {
            "album": self._adapter.play_album,
            "artist": self._adapter.play_artist,
            "track": self._adapter.play_track,
            "playlist": self._adapter.play_playlist,
        }[kind]
        return await self._started(
            kind, name, playing(name), asked_for=spoken, instead_of=asked_for
        )

    async def _find(self, spoken: str, prefer: str) -> tuple[str, str] | None:
        """The kind that was asked for first, then the others.

        Tracks come late among the others because there are 3975 of them and
        one word matches a great many: a name that is also an album or an
        artist is more likely to have meant those. Asked for a song, though,
        songs are looked at first.
        """
        order = ["album", "artist", "track", "playlist"]
        if prefer in order:
            order.remove(prefer)
            order.insert(0, prefer)

        listing = {
            "album": self._adapter.albums,
            "artist": self._adapter.artists,
            "track": self._adapter.tracks,
            "playlist": self._adapter.playlists,
        }

        for kind in order:
            found = closest(spoken, await listing[kind]())
            if found is not None:
                return kind, found

        return None

    async def _started(
        self,
        kind: str,
        name: str,
        playing: Awaitable[str],
        *,
        asked_for: str | None = None,
        instead_of: str | None = None,
    ) -> ToolResult:
        started_at = await playing
        # An edition of the same thing is not "nothing called that": the
        # library simply spells it with the year of the remaster on the end.
        #
        # Same kind, though. A playlist standing in for an album is a
        # substitution however alike the names are, and saying so is how a
        # wrong guess stays audible.
        an_edition = (
            asked_for is not None
            and (instead_of is None or instead_of == kind)
            and " ".join(name.casefold().split()).startswith(
                " ".join(asked_for.casefold().split())
            )
        )
        speech = (
            self._speaker.say(
                "music.playing_instead",
                asked=asked_for,
                # A word in the language being spoken, not the enum's spelling:
                # "A tocar album X" is not a sentence anyone says.
                kind=self._speaker.say(f"kind.{kind}"),
                name=name,
            )
            if asked_for and not an_edition
            else self._speaker.say("music.playing", name=name)
        )
        return ToolResult.success(
            PLAY,
            data={
                "name": name,
                "kind": kind,
                "started_at": started_at,
                **({"asked_for": asked_for} if asked_for else {}),
                **({"asked_kind": instead_of} if instead_of else {}),
            },
            speech=speech,
        )

    async def _playlist(self, spoken: str) -> ToolResult:
        existing = await self._adapter.playlists()
        name = closest(spoken, existing)

        if name is None:
            # Naming a few is the difference between "it did not work" and
            # knowing what to say instead.
            suggestions = ", ".join(existing[:5]) or "none"
            return ToolResult.failure(
                PLAY,
                ToolErrorCode.INVALID_ARGUMENTS,
                self._speaker.say(
                    "music.no_playlist", name=spoken, existing=suggestions
                ),
            )

        started_at = await self._adapter.play_playlist(name)
        return ToolResult.success(
            PLAY,
            data={"name": name, "kind": "playlist", "started_at": started_at},
            speech=self._speaker.say("music.playing", name=name),
        )

    async def control(self, args: ControlArgs) -> ToolResult:
        playing = await self._adapter.control(args.action)

        key = SPOKEN[args.action]
        if playing and args.action in WITH_TRACK:
            key = f"{key}_track"

        return ToolResult.success(
            CONTROL,
            data={"action": args.action, "track": playing},
            speech=self._speaker.say(key, track=playing),
        )

    async def seek(self, args: SeekArgs) -> ToolResult:
        landed = await self._adapter.seek(args.to)
        if not landed:
            return ToolResult.failure(
                SEEK,
                ToolErrorCode.INVALID_ARGUMENTS,
                self._speaker.say("music.nothing_playing"),
            )

        where = _seconds(landed)
        return ToolResult.success(
            SEEK,
            data={"at": where},
            # Where it landed, not where it was asked for: the script clamps,
            # and announcing the request would be announcing a guess.
            speech=self._speaker.say("music.seeked", when=_clock(where)),
        )

    async def now_playing(self, _args: NowPlayingArgs) -> ToolResult:
        """What is playing, for a display to draw.

        Changes nothing. It still goes through the same door and the same
        application level as everything else that reaches into Music -- the
        level governs whether E.V. may touch the application at all, and
        reading it is touching it.
        """
        (
            state,
            name,
            artist,
            album,
            at,
            length,
            shuffle,
            repeating,
            cover,
            words,
        ) = await self._adapter.now_playing(self._artwork)

        return ToolResult.success(
            NOW_PLAYING,
            data={
                "state": state,
                "track": name,
                "artist": artist,
                "album": album,
                "at": _seconds(at),
                "length": _seconds(length),
                "shuffle": shuffle == "on",
                "repeat": repeating,
                "cover": self._cover(cover, name, album),
                # Whatever the file carries. Apple Music's streamed catalogue
                # keeps its own time-synced lyrics to itself, so this is empty
                # for almost everything -- and empty is the honest answer
                # rather than a reason to go and fetch some.
                "lyrics": words.strip(),
            },
            # Nothing is said out loud: this is a display reading itself, and
            # a status line spoken every second is not an assistant.
            speech=None,
        )

    def _cover(self, wrote: str, track: str, album: str) -> str | None:
        """The cover as a data URL, re-read only when the record changes.

        Artwork is a few hundred kilobytes and the display asks every second;
        the file is only rewritten when Music has a different record open, and
        the bytes are only turned into a string that often too.
        """
        if not wrote:
            return None

        seen = f"{album}\u0000{track}"
        if seen == self._seen and self._cover_url is not None:
            return self._cover_url

        try:
            raw = Path(wrote).read_bytes()
        except OSError:
            return None

        kind = next(
            (mime for magic, mime in COVER_TYPES.items() if raw.startswith(magic)),
            None,
        )
        if kind is None:
            return None

        self._seen = seen
        self._cover_url = f"data:{kind};base64,{b64encode(raw).decode('ascii')}"
        return self._cover_url

    async def mode(self, args: ModeArgs) -> ToolResult:
        now = await self._adapter.mode(args.setting, args.state)

        key = SWITCHED.get((args.setting, now))
        if key is None:
            # Music answered with a position that is not one of its three.
            # Saying so beats reading an empty string out loud.
            return ToolResult.failure(
                MODE,
                ToolErrorCode.ADAPTER_FAILED,
                self._speaker.say("music.switch_failed", setting=args.setting),
            )

        return ToolResult.success(
            MODE,
            data={"setting": args.setting, "state": now},
            speech=self._speaker.say(key),
        )

    async def volume(self, args: VolumeArgs) -> ToolResult:
        if args.level is not None:
            now = await self._adapter.volume(args.level)
        elif args.change == "up":
            now = await self._adapter.step(STEP)
        elif args.change == "down":
            now = await self._adapter.step(-STEP)
        else:
            now = await self._adapter.mute(args.change == "mute")

        if args.change in {"mute", "unmute"}:
            return ToolResult.success(
                VOLUME,
                data={"change": args.change},
                speech=self._speaker.say(
                    "music.muted" if args.change == "mute" else "music.unmuted"
                ),
            )

        return ToolResult.success(
            VOLUME,
            data={"level": now or args.level, "change": args.change},
            speech=self._speaker.say("music.volume", level=now or args.level),
        )
