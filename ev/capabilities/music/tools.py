"""Registry entries. Declaration only, no logic."""

from __future__ import annotations

from typing import Any

from ev.capabilities.music.args import (
    ControlArgs,
    ModeArgs,
    NowPlayingArgs,
    PlayArgs,
    SeekArgs,
    VolumeArgs,
)
from ev.capabilities.music.service import (
    CONTROL,
    MODE,
    NOW_PLAYING,
    PLAY,
    SEEK,
    VOLUME,
    MusicService,
)
from ev.domain.permissions import Permission
from ev.domain.risk import RiskLevel
from ev.registry import ToolSpec

# Sending an Apple Event to Music is what TCC gates. Until the host reports it
# granted -- or the user asserts it with --grant -- the policy denies these
# before macOS is ever asked.
APPLE_EVENTS = frozenset({Permission.APPLE_EVENTS})


def music_tools(service: MusicService) -> tuple[ToolSpec[Any], ...]:
    return (
        ToolSpec(
            name=PLAY,
            description=(
                "Play an album, track or playlist from the local Music library. "
                "An album plays through from the beginning."
            ),
            args=PlayArgs,
            risk=RiskLevel.SENSITIVE,
            handler=service.play,
            permissions=APPLE_EVENTS,
            # Always this one, so the level set for it governs every call.
            application=lambda _args: "Music",
        ),
        ToolSpec(
            name=CONTROL,
            description=(
                "Control what is already playing: pause, resume, next, previous, stop."
            ),
            args=ControlArgs,
            risk=RiskLevel.SENSITIVE,
            handler=service.control,
            permissions=APPLE_EVENTS,
            # Always this one, so the level set for it governs every call.
            application=lambda _args: "Music",
        ),
        ToolSpec(
            name=MODE,
            description=(
                "Turn shuffle or repeat on or off. Left alone, the state flips "
                "-- saying 'shuffle' is pressing the button. Repeat also takes "
                "'one' for repeating the current track."
            ),
            args=ModeArgs,
            risk=RiskLevel.SENSITIVE,
            handler=service.mode,
            permissions=APPLE_EVENTS,
            # Always this one, so the level set for it governs every call.
            application=lambda _args: "Music",
        ),
        ToolSpec(
            name=SEEK,
            description=(
                "Move the playhead within the track that is playing: "
                "'skip to 1:30', 'avança para 2:04'. Seconds from the start."
            ),
            args=SeekArgs,
            risk=RiskLevel.SENSITIVE,
            handler=service.seek,
            permissions=APPLE_EVENTS,
            # Always this one, so the level set for it governs every call.
            application=lambda _args: "Music",
        ),
        ToolSpec(
            name=NOW_PLAYING,
            description=(
                "What Music is playing right now: track, artist, album, how "
                "far in, and whether shuffle and repeat are on. Changes "
                "nothing."
            ),
            args=NowPlayingArgs,
            risk=RiskLevel.SAFE,
            handler=service.now_playing,
            permissions=APPLE_EVENTS,
            # Same application, same level: reading Music is still reaching
            # into Music, and the level governs whether E.V. may.
            application=lambda _args: "Music",
            # A display asks this every second while it is open. The journal
            # records what E.V. did to the machine, and this did nothing --
            # see docs/adr/0038.
            journalled=False,
        ),
        ToolSpec(
            name=VOLUME,
            description="Set Music's own volume, 0 to 100. Not the system volume.",
            args=VolumeArgs,
            risk=RiskLevel.SENSITIVE,
            handler=service.volume,
            permissions=APPLE_EVENTS,
            # Always this one, so the level set for it governs every call.
            application=lambda _args: "Music",
        ),
    )
