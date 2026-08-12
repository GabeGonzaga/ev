"""Registry entries. Declaration only, no logic."""

from __future__ import annotations

from typing import Any

from ev.capabilities.music.args import ControlArgs, PlayArgs, VolumeArgs
from ev.capabilities.music.service import CONTROL, PLAY, VOLUME, MusicService
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
        ),
        ToolSpec(
            name=VOLUME,
            description="Set Music's own volume, 0 to 100. Not the system volume.",
            args=VolumeArgs,
            risk=RiskLevel.SENSITIVE,
            handler=service.volume,
            permissions=APPLE_EVENTS,
        ),
    )
