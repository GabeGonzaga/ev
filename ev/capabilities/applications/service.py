"""Orchestration. Never touches the system directly.

One thing happens here before any adapter call: the spoken name is matched
against what is installed. `Visual Studio Code` is dictated as "visual studio
code", "vs code" and "code", and `open -a` given the wrong one launches the
wrong application rather than failing.

What E.V. may then do with it is not decided here. The application's access
level is the user's, and `Registry.call()` reads it (ADR 0033) -- this service
is reached only once that has been satisfied.
"""

from __future__ import annotations

from ev.application.speech import Speaker
from ev.capabilities.applications.adapters import ApplicationAdapter
from ev.capabilities.applications.args import ApplicationArgs
from ev.domain.naming import closest
from ev.domain.results import ToolErrorCode, ToolResult
from ev.infrastructure.macos.applications import Applications

OPEN = "applications.open"
QUIT = "applications.quit"


def installed_name(applications: Applications, spoken: str) -> str | None:
    """The application someone meant, or nothing.

    Nothing rather than a guess: launching the wrong application is a visible,
    annoying, occasionally alarming thing to do on someone's behalf.
    """
    return closest(spoken, applications.installed())


class ApplicationService:
    def __init__(
        self,
        adapter: ApplicationAdapter,
        applications: Applications,
        speaker: Speaker | None = None,
    ) -> None:
        self._adapter = adapter
        self._applications = applications
        self._speaker = speaker or Speaker()

    async def open(self, args: ApplicationArgs) -> ToolResult:
        name = self._resolve(args.name)
        if name is None:
            return self._unknown(OPEN, args.name)

        await self._adapter.open(name)
        return ToolResult.success(
            OPEN,
            data={"name": name, "asked_for": args.name},
            speech=self._speaker.say("applications.opened", name=name),
        )

    async def quit(self, args: ApplicationArgs) -> ToolResult:
        name = self._resolve(args.name)
        if name is None:
            return self._unknown(QUIT, args.name)

        await self._adapter.quit(name)
        return ToolResult.success(
            QUIT,
            data={"name": name, "asked_for": args.name},
            speech=self._speaker.say("applications.quit", name=name),
        )

    def _resolve(self, spoken: str) -> str | None:
        return installed_name(self._applications, spoken)

    def _unknown(self, tool: str, spoken: str) -> ToolResult:
        return ToolResult.failure(
            tool,
            ToolErrorCode.INVALID_ARGUMENTS,
            self._speaker.say("applications.unknown", name=spoken),
        )
