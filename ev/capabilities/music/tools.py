"""Registry entries. Declaration only, no logic."""

from __future__ import annotations

from typing import Any

from ev.capabilities.music.args import PlayArgs
from ev.capabilities.music.service import PLAY, MusicService
from ev.domain.permissions import Permission
from ev.domain.risk import RiskLevel
from ev.registry import ToolSpec


def music_tools(service: MusicService) -> tuple[ToolSpec[Any], ...]:
    return (
        ToolSpec(
            name=PLAY,
            description=(
                "Play an album, track or playlist from the local Music library."
            ),
            args=PlayArgs,
            risk=RiskLevel.SENSITIVE,
            handler=service.play,
            # Sending an Apple Event to Music is what TCC gates. Until the host
            # reports it granted -- or the user asserts it with --grant -- the
            # policy denies this before macOS is ever asked.
            permissions=frozenset({Permission.APPLE_EVENTS}),
        ),
    )
