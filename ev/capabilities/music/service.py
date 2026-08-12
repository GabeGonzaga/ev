"""Orchestration. Never touches the system directly.

Two things happen here that are not adapter calls, and both are the same idea:
a spoken name is matched against what actually exists rather than passed
through. `CLAUDE.md` states it for shortcuts -- "the name is resolved against
the real list, never passed through freely" -- and a playlist called
`GO w/Flow!!` is why it matters for music too.
"""

from __future__ import annotations

import re

from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.args import ControlArgs, PlayArgs, VolumeArgs
from ev.domain.results import ToolErrorCode, ToolResult
from ev.infrastructure.macos.applescript import AppleScriptError

PLAY = "music.play"
CONTROL = "music.control"
VOLUME = "music.volume"

_NOISE = re.compile(r"[^\w]+", re.UNICODE)

NOT_FOUND = "nothing in the library matches"
"""What the album and track scripts say when a name is not in the library.
Matched here so a miss can be turned into something useful rather than
repeated back at the user."""

SPOKEN = {
    "pause": "Paused",
    "resume": "Playing",
    "next": "Skipped",
    "previous": "Went back",
    "stop": "Stopped",
}


def simplify(name: str) -> str:
    """What a name sounds like, with the punctuation nobody says removed.

    `{Jazzy}`, `Indie kid??` and `Main PlayList :D` are real playlist names.
    Nobody dictates the braces.
    """
    return _NOISE.sub("", name).casefold()


def closest(spoken: str, existing: list[str]) -> str | None:
    """The playlist someone meant, or nothing.

    Exact first, then punctuation-blind, then a unique prefix or containment.
    Ambiguity returns nothing rather than a guess: playing the wrong playlist
    is worse than saying which ones matched.
    """
    for name in existing:
        if name == spoken:
            return name

    wanted = simplify(spoken)
    if not wanted:
        return None

    simple = [(simplify(name), name) for name in existing]

    exact = [name for key, name in simple if key == wanted]
    if len(exact) == 1:
        return exact[0]

    partial = [name for key, name in simple if key.startswith(wanted) or wanted in key]
    return partial[0] if len(partial) == 1 else None


class MusicService:
    def __init__(self, adapter: MusicAdapter) -> None:
        self._adapter = adapter

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
            speech = f"Playing {args.name}"
            if started_at and started_at != args.name:
                speech = f"{speech}, from {started_at}"
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
            speech=f"Playing {args.name}",
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
            speech=f"No album called {spoken}. Playing the playlist {name}",
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
                f"no playlist matches {spoken!r}. You have: {suggestions}",
            )

        started_at = await self._adapter.play_playlist(name)
        return ToolResult.success(
            PLAY,
            data={"name": name, "kind": "playlist", "started_at": started_at},
            speech=f"Playing {name}",
        )

    async def control(self, args: ControlArgs) -> ToolResult:
        playing = await self._adapter.control(args.action)

        said = SPOKEN[args.action]
        if playing and args.action in {"resume", "next", "previous"}:
            said = (
                f"{said} to {playing}"
                if args.action != "resume"
                else f"{said} {playing}"
            )

        return ToolResult.success(
            CONTROL, data={"action": args.action, "track": playing}, speech=said
        )

    async def volume(self, args: VolumeArgs) -> ToolResult:
        level = await self._adapter.volume(args.level)
        return ToolResult.success(
            VOLUME, data={"level": args.level}, speech=f"Volume {level or args.level}"
        )
