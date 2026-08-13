"""Registry entries. Declaration only, no logic."""

from __future__ import annotations

from typing import Any

from ev.capabilities.notes.args import CreateArgs
from ev.capabilities.notes.service import CREATE, NotesService
from ev.domain.permissions import Permission
from ev.domain.risk import RiskLevel
from ev.registry import ToolSpec

APPLE_EVENTS = frozenset({Permission.APPLE_EVENTS})


def notes_tools(service: NotesService) -> tuple[ToolSpec[Any], ...]:
    return (
        ToolSpec(
            name=CREATE,
            description=(
                "Save a note in the Notes app. The title is the user's own "
                "words; the body is the only field that may be written for them."
            ),
            args=CreateArgs,
            # It writes, and it writes where the user can see it. Nothing is
            # overwritten and nothing is deleted, so it is not DESTRUCTIVE and
            # does not stop to confirm -- a note that had to be approved twice
            # is slower than typing it.
            risk=RiskLevel.SENSITIVE,
            handler=service.create,
            permissions=APPLE_EVENTS,
            # Always this one, so the level set for it governs every call.
            application=lambda _args: "Notes",
        ),
    )
