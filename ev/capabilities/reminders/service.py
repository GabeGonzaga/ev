"""Orchestration. Never touches the system directly.

Two things happen here that are not adapter calls: a spoken list name is
matched against the lists that exist, and a due date is checked against the
clock.

The second is new. Every other argument E.V. takes is a name someone said,
which is either right or unrecognised. A date is computed by the model, and
the way a model gets a date wrong is to be confidently in the wrong year --
which Reminders accepts, fires immediately, and calls a success.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from ev.application.speech import Speaker
from ev.capabilities.reminders.adapters import NO_LIST, RemindersAdapter
from ev.capabilities.reminders.args import CreateArgs
from ev.domain.naming import closest
from ev.domain.results import ToolErrorCode, ToolResult
from ev.infrastructure.macos.applescript import AppleScriptError

CREATE = "reminders.create"

GRACE = timedelta(hours=1)
"""How far into the past a due date may be.

Not zero: "remind me at nine" said at 9:02 is a real request, and so is a turn
that took a second to route. A year ago is not, and that is the shape the
mistake actually takes.
"""

WHEN = "%d/%m %H:%M"
"""Day before month, 24 hours. The same in both locales E.V. speaks, and the
one the user reads on this machine."""


def _now() -> datetime:
    return datetime.now()


class RemindersService:
    def __init__(
        self,
        adapter: RemindersAdapter,
        speaker: Speaker | None = None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._adapter = adapter
        self._speaker = speaker or Speaker()
        self._clock = clock

    async def create(self, args: CreateArgs) -> ToolResult:
        due = self._local(args.due)

        if due is not None and due < self._clock() - GRACE:
            # A reminder in the past fires the moment it is made, which reads
            # as "it worked" and is not what was asked for. Saying the date
            # back is what makes a wrong year visible.
            return ToolResult.failure(
                CREATE,
                ToolErrorCode.INVALID_ARGUMENTS,
                self._speaker.say("reminders.past", when=due.strftime(WHEN)),
            )

        name: str | None = None
        if args.list is not None:
            existing = await self._adapter.lists()
            name = closest(args.list, existing)
            if name is None:
                suggestions = ", ".join(existing[:5]) or "none"
                return ToolResult.failure(
                    CREATE,
                    ToolErrorCode.INVALID_ARGUMENTS,
                    self._speaker.say(
                        "reminders.no_list", name=args.list, existing=suggestions
                    ),
                )

        try:
            title = await self._adapter.create(args.title, due, name)
        except AppleScriptError as error:
            code = (
                ToolErrorCode.INVALID_ARGUMENTS
                if NO_LIST in str(error)
                else ToolErrorCode.ADAPTER_FAILED
            )
            return ToolResult.failure(CREATE, code, str(error))

        return ToolResult.success(
            CREATE,
            data={
                "title": title,
                "list": name,
                "due": due.isoformat() if due else None,
            },
            speech=(
                self._speaker.say(
                    "reminders.created_at", title=title, when=due.strftime(WHEN)
                )
                if due
                else self._speaker.say("reminders.created", title=title)
            ),
        )

    def _local(self, due: datetime | None) -> datetime | None:
        """Naive local time, which is what a person means and what AppleScript
        builds from `current date`.

        A model asked for ISO 8601 sometimes writes an offset or a `Z`. That is
        an answerable question -- convert it -- rather than a reason to refuse.
        """
        if due is None or due.tzinfo is None:
            return due
        return due.astimezone(datetime.now(UTC).astimezone().tzinfo).replace(
            tzinfo=None
        )
