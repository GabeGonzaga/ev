"""The one door to AppleScript.

The script is a constant owned by an adapter. Values reach it as `argv` and are
read with `item n of argv`, so nothing is ever interpolated into the source --
which is what makes an album called `" & do shell script "rm -rf ~` a string
and not a program. This is invariant 2 for the AppleScript route: the model
cannot supply a complete script, and it cannot supply a fragment of one either.

`osascript -e '<constant>' -- <values>` is the whole mechanism.
"""

from __future__ import annotations

import re
from typing import Final

from ev.infrastructure.macos.processes import ProcessFailed, ProcessRunner

APPLESCRIPT_TIMEOUT: Final = 20.0
"""Longer than a subprocess needs, shorter than a hung application. Music can
take a moment to launch before it answers the first event."""

_ERROR_CODE = re.compile(r"\s*\(-?\d+\)\s*$")


class AppleScriptError(Exception):
    """What the script or the system said, cleaned up enough to be spoken."""


def _message(stderr: str) -> str:
    text = stderr.strip().removeprefix("execution error: ")
    return _ERROR_CODE.sub("", text) or "osascript failed"


class AppleScriptClient:
    def __init__(self, processes: ProcessRunner) -> None:
        self._processes = processes

    async def run(
        self, script: str, *arguments: str, timeout: float = APPLESCRIPT_TIMEOUT
    ) -> str:
        try:
            completed = await self._processes.run(
                ["osascript", "-e", script, "--", *arguments], timeout=timeout
            )
        except ProcessFailed as failure:
            # A refused Apple Event arrives here too, with the system's own
            # wording. That is the message worth repeating to the user.
            raise AppleScriptError(_message(failure.completed.stderr)) from failure

        return completed.stdout.strip()
