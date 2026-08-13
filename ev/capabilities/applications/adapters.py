"""The boundary. The only code in this capability that talks to macOS.

Two ways in, and the order is the one `CLAUDE.md` sets. Quitting goes through
the scripting dictionary, because every application has `quit` and it lets the
application put its own documents away. Launching goes through `open -a`,
because there is no dictionary to address before an application is running.

The name reaching either has already been matched against what is installed.
"""

from __future__ import annotations

from typing import Final

from ev.infrastructure.macos.applescript import AppleScriptClient
from ev.infrastructure.macos.processes import ProcessRunner

QUIT: Final = """on run argv
	set theName to item 1 of argv
	tell application theName to quit
	return theName
end run"""
"""`tell application theName` -- a variable, not an interpolation. The name is
`item 1 of argv`, so an application called `Music" & do shell script "rm` is a
name that matches nothing rather than a program."""

ACTIVATE: Final = """on run argv
	set theName to item 1 of argv
	tell application theName to activate
	return theName
end run"""


class ApplicationAdapter:
    def __init__(
        self, processes: ProcessRunner, applescript: AppleScriptClient
    ) -> None:
        self._processes = processes
        self._applescript = applescript

    async def open(self, name: str) -> None:
        # `-a` by name: `open` resolves it through Launch Services, which is
        # the same lookup the Dock and Spotlight use. No path, no bundle id,
        # nothing the model chose.
        await self._processes.run(["open", "-a", name])

    async def quit(self, name: str) -> str:
        return await self._applescript.run(QUIT, name)

    async def activate(self, name: str) -> str:
        return await self._applescript.run(ACTIVATE, name)
