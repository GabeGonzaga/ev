"""The boundary. The only code in this capability that talks to macOS.

Every script is a constant and every value arrives as `argv`.

A date is the awkward one. AppleScript's `date "..."` parses a string against
the machine's own date format, so the same source means different days on two
Macs -- and reading `13/08/2026` as August 13th or as an error is exactly the
kind of failure that looks like a success. The date is therefore never written
as text: it is built from integers, in the script, out of `current date`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from ev.infrastructure.macos.applescript import AppleScriptClient

LIST_LISTS: Final = """on run argv
	tell application "Reminders"
		set theNames to name of every list
	end tell
	set AppleScript's text item delimiters to linefeed
	return theNames as text
end run"""

CREATE: Final = """on run argv
	set theTitle to item 1 of argv
	set listName to item 2 of argv
	set theDate to missing value
	if (item 3 of argv) is not "" then
		set theDate to current date
		set day of theDate to 1
		set year of theDate to (item 3 of argv) as integer
		set month of theDate to (item 4 of argv) as integer
		set day of theDate to (item 5 of argv) as integer
		set time of theDate to (item 6 of argv) as integer
	end if
	tell application "Reminders"
		if listName is "" then
			set theList to default list
		else
			if not (exists list listName) then
				error "there is no list called " & listName
			end if
			set theList to list listName
		end if
		set props to {name:theTitle}
		if theDate is not missing value then
			set props to props & {due date:theDate}
		end if
		set theReminder to make new reminder at theList with properties props
		return name of theReminder
	end tell
end run"""
"""`set day to 1` before the year and the month is not superstition.

Setting the month while the day is the 31st rolls the date forward: on the
31st of January, `set month to February` gives the 3rd of March. Anchoring the
day first is the fix, and the reason the order looks strange.

`current date` is asked for before the `tell` block. It is a Standard Additions
command, not something Reminders answers, and this file has been bitten once by
sending a global to an application (`text item delimiters`, ADR 0023).
"""

NO_LIST = "there is no list called"
"""What `CREATE` says when the list is gone between listing and writing."""

SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60


def seconds_into_the_day(due: datetime) -> int:
    """AppleScript's `time` property is seconds since midnight.

    Computed here rather than in the script: arithmetic in Python is testable
    and arithmetic in a string is not.
    """
    return due.hour * SECONDS_PER_HOUR + due.minute * SECONDS_PER_MINUTE + due.second


class RemindersAdapter:
    def __init__(self, applescript: AppleScriptClient) -> None:
        self._applescript = applescript

    async def lists(self) -> list[str]:
        answer = await self._applescript.run(LIST_LISTS)
        return [line.strip() for line in answer.splitlines() if line.strip()]

    async def create(
        self, title: str, due: datetime | None, list_name: str | None
    ) -> str:
        # Empty strings, not missing items: the script reads six arguments
        # unconditionally, and a short argv would fail inside AppleScript
        # rather than here.
        when = (
            [
                str(due.year),
                str(due.month),
                str(due.day),
                str(seconds_into_the_day(due)),
            ]
            if due is not None
            else ["", "", "", ""]
        )
        return await self._applescript.run(CREATE, title, list_name or "", *when)
