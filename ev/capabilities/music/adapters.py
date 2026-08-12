"""The boundary. The only code in this capability that talks to macOS.

Every script is a constant. Names and numbers arrive as `argv` and are read
with `item n of argv`, so an album called `" & do shell script "rm -rf ~` is a
string and not a program.
"""

from __future__ import annotations

from typing import Final

from ev.infrastructure.macos.applescript import AppleScriptClient

QUEUE = "E.V. queue"
"""E.V.'s own playlist, rebuilt for each album and never anything else.

An album cannot be played by handing `play` a list: Music's dictionary takes a
single item, and playing one track plays one track -- which is what the first
version did, and what actually happened when it met a real album. A playlist
is the only thing Music will play through, so E.V. keeps exactly one and
replaces its contents. It is visible in the sidebar on purpose: a program that
edits your library should do so where you can see it.
"""

LIST_PLAYLISTS: Final = """on run argv
	tell application "Music"
		set theNames to name of every user playlist
	end tell
	set AppleScript's text item delimiters to linefeed
	return theNames as text
end run"""
"""The delimiter is set outside the `tell`, and named as AppleScript's.

`text item delimiters` belongs to AppleScript, not to Music. Setting it inside
the block sends it to Music, which answers "Can't set text item delimiters" at
runtime -- and compiles perfectly, because the syntax was never the problem.
"""

PLAY_ALBUM: Final = """on run argv
	set theName to item 1 of argv
	set queueName to item 2 of argv
	tell application "Music"
		set lib to library playlist 1
		set matches to (every track of lib whose album is theName)
		if matches is {} then
			error "nothing in the library matches " & theName
		end if
		if (exists user playlist queueName) then
			delete user playlist queueName
		end if
		set theQueue to make new user playlist with properties {name:queueName}
		duplicate matches to theQueue
		play theQueue
		return name of current track
	end tell
end run"""

PLAY_TRACK: Final = """on run argv
	set theName to item 1 of argv
	tell application "Music"
		set lib to library playlist 1
		set matches to (every track of lib whose name is theName)
		if matches is {} then
			error "nothing in the library matches " & theName
		end if
		play item 1 of matches
		return name of current track
	end tell
end run"""

PLAY_PLAYLIST: Final = """on run argv
	set theName to item 1 of argv
	tell application "Music"
		if not (exists user playlist theName) then
			error "there is no playlist called " & theName
		end if
		play user playlist theName
		return name of current track
	end tell
end run"""

CONTROL: Final = """on run argv
	set theAction to item 1 of argv
	tell application "Music"
		if theAction is "pause" then
			pause
		else if theAction is "resume" then
			play
		else if theAction is "next" then
			next track
		else if theAction is "previous" then
			previous track
		else if theAction is "stop" then
			stop
		end if
		return my nowPlaying()
	end tell
end run

on nowPlaying()
	tell application "Music"
		try
			if player state is stopped then return ""
			return name of current track
		on error
			-- Skipping past the end of a queue, or a track Music can no
			-- longer reach, leaves a player that is not stopped and has no
			-- current track. It happened; "Music got an error: Can't get name
			-- of current track" is a real line from the journal. The action
			-- worked, so the answer is what is playing -- nothing.
			return ""
		end try
	end tell
end nowPlaying"""

VOLUME: Final = """on run argv
	tell application "Music"
		set sound volume to (item 1 of argv) as integer
		return (sound volume as text)
	end tell
end run"""

STEP: Final = """on run argv
	set theStep to (item 1 of argv) as integer
	tell application "Music"
		set wanted to (sound volume) + theStep
		if wanted > 100 then set wanted to 100
		if wanted < 0 then set wanted to 0
		set sound volume to wanted
		return (sound volume as text)
	end tell
end run"""

MUTE: Final = """on run argv
	tell application "Music"
		set mute to (item 1 of argv is "true")
		return (sound volume as text)
	end tell
end run"""


class MusicAdapter:
    def __init__(self, applescript: AppleScriptClient) -> None:
        self._applescript = applescript

    async def playlists(self) -> list[str]:
        """Every playlist, by name. A spoken name is matched against these
        rather than passed through: "GO w/Flow!!" is not something anyone
        dictates exactly."""
        answer = await self._applescript.run(LIST_PLAYLISTS)
        return [line.strip() for line in answer.splitlines() if line.strip()]

    async def play_album(self, name: str) -> str:
        return await self._applescript.run(PLAY_ALBUM, name, QUEUE)

    async def play_track(self, name: str) -> str:
        return await self._applescript.run(PLAY_TRACK, name)

    async def play_playlist(self, name: str) -> str:
        return await self._applescript.run(PLAY_PLAYLIST, name)

    async def control(self, action: str) -> str:
        return await self._applescript.run(CONTROL, action)

    async def volume(self, level: int) -> str:
        return await self._applescript.run(VOLUME, str(level))

    async def step(self, by: int) -> str:
        """Relative, and clamped by Music rather than by guessing what it is
        set to now: reading and then writing would race with the person
        holding the volume key."""
        return await self._applescript.run(STEP, str(by))

    async def mute(self, silent: bool) -> str:
        """Music's own mute, so unmuting restores the level rather than
        inventing one."""
        return await self._applescript.run(MUTE, "true" if silent else "false")
