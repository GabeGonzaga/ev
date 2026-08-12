"""The boundary. The only code in this capability that talks to macOS.

Every script is a constant and every value arrives as `argv`, so a note called
`" & do shell script "rm -rf ~` is a title.

Notes stores a note's body as HTML, so the text has to be turned into HTML
somewhere. That happens in `render.py`, in Python rather than in AppleScript,
and this file only passes the result along -- an adapter that assembles strings
is the thing the architecture test is guarding against.
"""

from __future__ import annotations

from typing import Final

from ev.capabilities.notes.render import html
from ev.infrastructure.macos.applescript import AppleScriptClient

LIST_FOLDERS: Final = """on run argv
	tell application "Notes"
		set theNames to name of every folder
	end tell
	set AppleScript's text item delimiters to linefeed
	return theNames as text
end run"""
"""The delimiter is set outside the `tell`, and named as AppleScript's -- it
belongs to AppleScript, not to Notes. Inside the block it compiles and then
fails at runtime, which is exactly how it shipped once for Music."""

CREATE: Final = """on run argv
	set theTitle to item 1 of argv
	set theBody to item 2 of argv
	set folderName to item 3 of argv
	set props to {name:theTitle, body:theBody}
	tell application "Notes"
		if folderName is "" then
			set theNote to make new note with properties props
		else
			if not (exists folder folderName) then
				error "there is no folder called " & folderName
			end if
			set theNote to make new note at folder folderName with properties props
		end if
		return name of theNote
	end tell
end run"""
"""The title is set twice on purpose: as the `name` property, and as the first
line of the body.

Notes shows the first line of a note as its title in the list. Setting only
`name` leaves a note whose title and first line disagree; setting only the body
leaves `name` to be derived. Both agree here, and the note reads the way a
hand-written one does."""

NO_FOLDER = "there is no folder called"
"""What `CREATE` says when the folder is gone between listing and writing."""


class NotesAdapter:
    def __init__(self, applescript: AppleScriptClient) -> None:
        self._applescript = applescript

    async def folders(self) -> list[str]:
        answer = await self._applescript.run(LIST_FOLDERS)
        return [line.strip() for line in answer.splitlines() if line.strip()]

    async def create(self, title: str, body: str | None, folder: str | None) -> str:
        return await self._applescript.run(
            CREATE, title, html(title, body), folder or ""
        )
