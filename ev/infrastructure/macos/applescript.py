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
from collections.abc import Callable
from typing import Final

from ev.domain.permissions import Permission, PermissionState
from ev.infrastructure.macos.processes import ProcessFailed, ProcessRunner

Reporter = Callable[[Permission, PermissionState], None]
"""Where "macOS just answered about Apple Events" goes.

A callback rather than an import: this file is infrastructure and the ledger is
application, so the direction of the dependency is the caller's to choose."""

_REFUSED = ("not authorized to send apple events", "-1743", "not allowed to send")
"""What macOS says when Automation is off for E.V. Matched loosely on purpose:
the wording differs between the error text and the error number, and both
appear depending on which application was addressed."""

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
    def __init__(
        self, processes: ProcessRunner, report: Reporter | None = None
    ) -> None:
        self._processes = processes
        self._report = report

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
            message = _message(failure.completed.stderr)
            self._answered(
                PermissionState.DENIED
                if any(said in message.casefold() for said in _REFUSED)
                else None
            )
            raise AppleScriptError(message) from failure

        # An event that was delivered is the only proof of Automation there is,
        # and it is a better one than a person typing --grant.
        self._answered(PermissionState.GRANTED)
        return completed.stdout.strip()

    def _answered(self, state: PermissionState | None) -> None:
        """A script that failed for its own reasons says nothing about TCC.

        Only a refusal and a delivery are evidence; everything else -- a
        missing album, a syntax error, a timeout -- leaves the permission
        exactly as unknown as it was.
        """
        if state is not None and self._report is not None:
            self._report(Permission.APPLE_EVENTS, state)
