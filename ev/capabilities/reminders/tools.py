"""Registry entries. Declaration only, no logic."""

from __future__ import annotations

from typing import Any

from ev.capabilities.reminders.args import CreateArgs
from ev.capabilities.reminders.service import CREATE, RemindersService
from ev.domain.permissions import Permission
from ev.domain.risk import RiskLevel
from ev.registry import ToolSpec

APPLE_EVENTS = frozenset({Permission.APPLE_EVENTS})


def reminders_tools(service: RemindersService) -> tuple[ToolSpec[Any], ...]:
    return (
        ToolSpec(
            name=CREATE,
            description=(
                "Add a reminder in the Reminders app, optionally due at a "
                "date and time, optionally in a named list."
            ),
            args=CreateArgs,
            # Writes, overwrites nothing, deletes nothing. A reminder that had
            # to be confirmed would be slower than the Reminders app.
            risk=RiskLevel.SENSITIVE,
            handler=service.create,
            permissions=APPLE_EVENTS,
            # Always this one, so the level set for it governs every call.
            application=lambda _args: "Reminders",
        ),
    )
