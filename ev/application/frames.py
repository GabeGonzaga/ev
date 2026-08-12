"""The frame a turn is allowed to look at.

`CLAUDE.md`, invariant 8: the camera may not be started by ambiguous model
inference, and frames are not persisted by default. Both fall out of where the
frame comes from.

It is bound by the surface, before the turn, because a person pressed a button
that turned a camera on. The model never chooses it, never names it and cannot
ask for a different one -- `vision.look` has no argument that selects an image,
only a question about the one already here.

It lives for one turn. `clear()` runs in a `finally`, so a frame outlives its
turn only for as long as it takes to answer, and never reaches the journal:
the tool's arguments are the question, and the question is all the trail
records.
"""

from __future__ import annotations


class Frames:
    """One frame, or none. Bound per turn, under the same lock as everything
    else about a turn."""

    def __init__(self) -> None:
        self._frame: bytes | None = None

    def bind(self, frame: bytes | None) -> None:
        self._frame = frame

    def clear(self) -> None:
        self._frame = None

    @property
    def waiting(self) -> bool:
        return self._frame is not None

    def current(self) -> bytes | None:
        return self._frame
