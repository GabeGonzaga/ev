"""Orchestration. Never touches the system directly.

The spoken line says what happened rather than what was asked for. Music's
`play` takes a single item, so an album starts at one track and Music continues
from there in library order -- reporting "Playing Blonde" alone would be a
claim this capability cannot make. The track it actually started on is both
spoken and journalled.
"""

from __future__ import annotations

from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.args import PlayArgs
from ev.domain.results import ToolResult

PLAY = "music.play"


class MusicService:
    def __init__(self, adapter: MusicAdapter) -> None:
        self._adapter = adapter

    async def play(self, args: PlayArgs) -> ToolResult:
        started_at = await self._adapter.play(args.name, args.kind)

        speech = f"Playing {args.name}"
        if args.kind == "album" and started_at and started_at != args.name:
            speech = f"{speech}, from {started_at}"

        return ToolResult.success(
            PLAY,
            data={"name": args.name, "kind": args.kind, "started_at": started_at},
            speech=speech,
        )
