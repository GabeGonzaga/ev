"""The boundary. The only code in this capability that talks to macOS.

`PLAY` is a constant. The name and the kind arrive as `argv`, never inside it.
"""

from __future__ import annotations

from typing import Final

from ev.infrastructure.macos.applescript import AppleScriptClient

PLAY: Final = """on run argv
	set theName to item 1 of argv
	set theKind to item 2 of argv
	tell application "Music"
		if theKind is "playlist" then
			if not (exists playlist theName) then
				error "there is no playlist called " & theName
			end if
			play playlist theName
		else
			set lib to library playlist 1
			if theKind is "album" then
				set matches to (every track of lib whose album is theName)
			else
				set matches to (every track of lib whose name is theName)
			end if
			if matches is {} then
				error "nothing in the library matches " & theName
			end if
			set startAt to item 1 of matches
			if theKind is "album" then
				repeat with aTrack in matches
					if track number of aTrack is 1 then
						set startAt to contents of aTrack
						exit repeat
					end if
				end repeat
			end if
			play startAt
		end if
		return name of current track
	end tell
end run"""


class MusicAdapter:
    def __init__(self, applescript: AppleScriptClient) -> None:
        self._applescript = applescript

    async def play(self, name: str, kind: str) -> str:
        """Returns the track Music actually started on."""
        return await self._applescript.run(PLAY, name, kind)
