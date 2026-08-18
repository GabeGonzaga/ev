"""The boundary. The only code in this capability that talks to macOS."""

from __future__ import annotations

import plistlib
from pathlib import Path
from typing import Final

from ev.infrastructure.macos.applescript import AppleScriptClient
from ev.infrastructure.macos.processes import ProcessRunner

OPEN_TIMEOUT = 10.0

LAUNCH_SERVICES: Final = (
    Path.home()
    / "Library/Preferences/com.apple.LaunchServices"
    / "com.apple.launchservices.secure.plist"
)

KNOWN: Final = frozenset({"com.google.chrome", "com.apple.safari"})


def default_browser() -> str | None:
    """Which application the user set for http, as a bundle id.

    Read from Launch Services rather than assumed. Anything not in `KNOWN`
    answers None, so an unfamiliar browser gets a plain open instead of a
    script written for somebody else's dictionary.
    """
    try:
        settings = plistlib.loads(LAUNCH_SERVICES.read_bytes())
    except (OSError, plistlib.InvalidFileException):
        return None

    for handler in settings.get("LSHandlers", []):
        if handler.get("LSHandlerURLScheme") in {"http", "https"}:
            chosen = str(handler.get("LSHandlerRoleAll", "")).casefold()
            return chosen if chosen in KNOWN else None
    return None


SMALL_WINDOW: Final = """on run argv
	set theUrl to item 1 of argv
	set theApp to item 2 of argv
	set theBounds to {item 3 of argv as integer, item 4 of argv as integer, ¬
		item 5 of argv as integer, item 6 of argv as integer}
	if theApp is "com.google.chrome" then
		tell application "Google Chrome"
			activate
			set theWindow to make new window
			set URL of active tab of theWindow to theUrl
			set bounds of theWindow to theBounds
		end tell
		return "window"
	else if theApp is "com.apple.safari" then
		tell application "Safari"
			activate
			set theWindow to make new document with properties {URL:theUrl}
			set bounds of window 1 to theBounds
		end tell
		return "window"
	end if
	return ""
end run"""
"""A window of its own, sized and placed, in the browser the user chose.

Only the two browsers whose scripting dictionaries are known are driven this
way; anything else answers empty and the caller falls back to a plain open. A
named adapter per application is the rule (`CLAUDE.md`), and guessing at an
unknown browser's dictionary is how a named adapter becomes a generic one.

The page is fetched by the browser, as it is for a tab. What changes here is
the shape of somebody else's window."""


class OpenAdapter:
    """`open(1)`: hand a URL to whatever the user set as their default browser."""

    def __init__(
        self, processes: ProcessRunner, applescript: AppleScriptClient | None = None
    ) -> None:
        self._processes = processes
        self._applescript = applescript

    async def open_url(self, url: str) -> None:
        # "--" ends option parsing, so a URL that starts with "-" is a URL and
        # not a flag. The adapter owns every element of this list.
        await self._processes.run(["open", "--", url], timeout=OPEN_TIMEOUT)

    async def open_small(self, url: str, where: tuple[int, int, int, int]) -> bool:
        """A small window, if the default browser is one we can ask.

        Answers whether it happened, so the caller can fall back rather than
        pretend.
        """
        if self._applescript is None:
            return False

        browser = default_browser()
        if browser is None:
            return False

        answer = await self._applescript.run(
            SMALL_WINDOW, url, browser, *(str(edge) for edge in where)
        )
        return answer.strip() == "window"
