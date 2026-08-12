"""Orchestration. Never touches the system directly.

Two things happen here that are not adapter calls, and both are the same idea:
a spoken name is matched against what actually exists rather than passed
through. `CLAUDE.md` states it for shortcuts -- "the name is resolved against
the real list, never passed through freely" -- and a playlist called
`GO w/Flow!!` is why it matters for music too.
"""

from __future__ import annotations

from ev.application.speech import Speaker
from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.args import STEP, ControlArgs, PlayArgs, VolumeArgs
from ev.domain.naming import closest
from ev.domain.results import ToolErrorCode, ToolResult
from ev.infrastructure.macos.applescript import AppleScriptError

PLAY = "music.play"
CONTROL = "music.control"
VOLUME = "music.volume"

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

WITH_TRACK = {"resume", "next", "previous"}
"""The three where naming what is playing now is the useful part of the
answer. Each has its own phrase, because "Skipped" and "Skipped to X" do not
compose by concatenation in every language -- pt-PT wants "para", not "to"."""


class MusicService:
    def __init__(self, adapter: MusicAdapter, speaker: Speaker | None = None) -> None:
        self._adapter = adapter
        self._speaker = speaker or Speaker()

    async def play(self, args: PlayArgs) -> ToolResult:
        if args.kind == "playlist":
            return await self._playlist(args.name)

        if args.kind == "album":
            try:
                started_at = await self._adapter.play_album(args.name)
            except AppleScriptError as error:
                return await self._not_an_album(args.name, error)
            # An album plays through now: E.V. builds its own playlist, which
            # is the only thing Music will play in order. Saying where it
            # started is still honest -- the queue begins somewhere.
            speech = (
                self._speaker.say(
                    "music.playing_from", name=args.name, track=started_at
                )
                if started_at and started_at != args.name
                else self._speaker.say("music.playing", name=args.name)
            )
            return ToolResult.success(
                PLAY,
                data={"name": args.name, "kind": "album", "started_at": started_at},
                speech=speech,
            )

        try:
            started_at = await self._adapter.play_track(args.name)
        except AppleScriptError as error:
            return await self._not_an_album(args.name, error)

        return ToolResult.success(
            PLAY,
            data={"name": args.name, "kind": "track", "started_at": started_at},
            speech=self._speaker.say("music.playing", name=args.name),
        )

    async def _not_an_album(self, spoken: str, error: AppleScriptError) -> ToolResult:
        """Nothing by that name -- but the name may be a playlist.

        This is the case that actually happened: a playlist called
        `Indie kid??`, asked for as an album, answered with "nothing in the
        library matches Indie Kid" while the thing sat in the sidebar. When
        exactly one playlist matches and no album does, there is no second
        reading to guess between, so it plays -- and says which, so a wrong
        guess is visible rather than silent.
        """
        if NOT_FOUND not in str(error):
            raise error

        name = closest(spoken, await self._adapter.playlists())
        if name is None:
            return ToolResult.failure(PLAY, ToolErrorCode.ADAPTER_FAILED, str(error))

        started_at = await self._adapter.play_playlist(name)
        return ToolResult.success(
            PLAY,
            data={
                "name": name,
                "kind": "playlist",
                "started_at": started_at,
                "asked_for": spoken,
            },
            speech=self._speaker.say("music.playing_instead", asked=spoken, name=name),
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
