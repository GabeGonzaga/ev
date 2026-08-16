"""The boundary. The only code in this capability that talks to macOS.

Every script is a constant. Names and numbers arrive as `argv` and are read
with `item n of argv`, so an album called `" & do shell script "rm -rf ~` is a
string and not a program.
"""

from __future__ import annotations

from typing import Final

from ev.infrastructure.macos.applescript import AppleScriptClient

MOST = 500
"""How many tracks E.V. will queue at once.

`duplicate` a whole artist's tracks in one statement and Music answers "Can't
set user playlist ... to {shared track id ...}" -- found by asking for Kendrick
Lamar, whose 112 tracks were too many for it. One at a time works, at about
19 ms each, so the loop is what plays anything now.

The bound follows from that: 500 tracks is 9 seconds, and the AppleScript
timeout is 20. Nobody asks for a queue that long on purpose, and a request
that would silently hit the timeout is worse than one that plays 500 tracks.
"""

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

LIST_ALBUMS: Final = """on run argv
	tell application "Music"
		set theNames to album of every track of library playlist 1
	end tell
	set AppleScript's text item delimiters to linefeed
	return theNames as text
end run"""
"""Every track's album, duplicates and all -- Music has no album object, only
a property on tracks. Deduplicated in Python, where a set is a set.

4229 tracks answered in 0.24 s on the machine this was written for, which is
why it is affordable to ask when a name does not match exactly."""

LIST_TRACKS: Final = """on run argv
	tell application "Music"
		set theNames to name of every track of library playlist 1
	end tell
	set AppleScript's text item delimiters to linefeed
	return theNames as text
end run"""
"""Every track name. 3975 of them here, 746 carrying a suffix nobody says --
`(Remastered)`, `(feat. ...)`, `(Live From Fenway Park)`. `Mona Lisa` exists
four times over, which is why the shortest prefix rule matters as much for
songs as it does for artists."""

LIST_ARTISTS: Final = """on run argv
	tell application "Music"
		set theNames to artist of every track of library playlist 1
	end tell
	set AppleScript's text item delimiters to linefeed
	return theNames as text
end run"""

PLAY_ARTIST: Final = """on run argv
	set theName to item 1 of argv
	set queueName to item 2 of argv
	set theLimit to (item 3 of argv) as integer
	tell application "Music"
		set lib to library playlist 1
		set matches to (every track of lib whose artist contains theName)
		if matches is {} then
			error "nothing in the library matches " & theName
		end if
		if (exists user playlist queueName) then
			delete user playlist queueName
		end if
		set theQueue to make new user playlist with properties {name:queueName}
		set queued to 0
		repeat with aTrack in matches
			if queued >= theLimit then exit repeat
			duplicate aTrack to theQueue
			set queued to queued + 1
		end repeat
		play theQueue
		return my nowPlaying()
	end tell
end run

on nowPlaying()
	tell application "Music"
		try
			if player state is stopped then return ""
			return name of current track
		on error
			return ""
		end try
	end tell
end nowPlaying"""
"""`contains`, not `is`. Half of what an artist recorded is credited to
`Kendrick Lamar & SZA` or `Future, Metro Boomin & Kendrick Lamar`, and someone
asking for Kendrick means those too. The name is resolved to the library's own
spelling before it gets here, so `contains` is matching a real artist rather
than a fragment somebody said."""

PLAY_ALBUM: Final = """on run argv
	set theName to item 1 of argv
	set queueName to item 2 of argv
	set theLimit to (item 3 of argv) as integer
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
		set queued to 0
		repeat with aTrack in matches
			if queued >= theLimit then exit repeat
			duplicate aTrack to theQueue
			set queued to queued + 1
		end repeat
		play theQueue
		return my nowPlaying()
	end tell
end run

on nowPlaying()
	tell application "Music"
		try
			if player state is stopped then return ""
			return name of current track
		on error
			return ""
		end try
	end tell
end nowPlaying"""

PLAY_TRACK: Final = """on run argv
	set theName to item 1 of argv
	tell application "Music"
		set lib to library playlist 1
		set matches to (every track of lib whose name is theName)
		if matches is {} then
			error "nothing in the library matches " & theName
		end if
		play item 1 of matches
		return my nowPlaying()
	end tell
end run

on nowPlaying()
	tell application "Music"
		try
			if player state is stopped then return ""
			return name of current track
		on error
			return ""
		end try
	end tell
end nowPlaying"""

PLAY_PLAYLIST: Final = """on run argv
	set theName to item 1 of argv
	tell application "Music"
		if not (exists user playlist theName) then
			error "there is no playlist called " & theName
		end if
		play user playlist theName
		return my nowPlaying()
	end tell
end run

on nowPlaying()
	tell application "Music"
		try
			if player state is stopped then return ""
			return name of current track
		on error
			return ""
		end try
	end tell
end nowPlaying"""

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

MODE: Final = """on run argv
	set theSetting to item 1 of argv
	set theState to item 2 of argv
	tell application "Music"
		if theSetting is "shuffle" then
			set wanted to (theState is "on")
			if theState is "toggle" then set wanted to not (shuffle enabled)
			set shuffle enabled to wanted
			if wanted then return "on"
			return "off"
		else if theSetting is "repeat" then
			set wanted to theState
			if wanted is "toggle" then
				if song repeat is off then
					set wanted to "all"
				else
					set wanted to "off"
				end if
			else if wanted is "on" then
				set wanted to "all"
			end if
			if wanted is "one" then
				set song repeat to one
			else if wanted is "all" then
				set song repeat to all
			else
				set song repeat to off
			end if
			return wanted
		end if
		return ""
	end tell
end run"""
"""What was set, not what Music says afterwards.

Reading a switch back immediately after writing it returns the old value:
`set shuffle enabled to true` followed by `shuffle enabled` answers false, and
answers true if a `delay 0.4` is put between them. The write lands, the read
races it. So this returns the value it decided on, which is the same lesson as
`name of current track` right after `play` -- measured here on Music 1.6.5,
macOS 26.5.2, where every write was verified to take and every immediate read
to lie.

Reading *before* writing is fine, which is what makes `toggle` honest: the
current state comes from Music rather than from something E.V. remembered, so
a switch somebody flipped in the app is the one being flipped back.

An unrecognised setting touches nothing and returns empty -- the read-only
path `make applescript` runs."""

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

    async def albums(self) -> list[str]:
        """Every album name in the library, once each."""
        return await self._unique(LIST_ALBUMS)

    async def artists(self) -> list[str]:
        return await self._unique(LIST_ARTISTS)

    async def tracks(self) -> list[str]:
        return await self._unique(LIST_TRACKS)

    async def _unique(self, script: str) -> list[str]:
        answer = await self._applescript.run(script)
        return sorted({line.strip() for line in answer.splitlines() if line.strip()})

    async def play_artist(self, name: str) -> str:
        return await self._applescript.run(PLAY_ARTIST, name, QUEUE, str(MOST))

    async def play_album(self, name: str) -> str:
        return await self._applescript.run(PLAY_ALBUM, name, QUEUE, str(MOST))

    async def play_track(self, name: str) -> str:
        return await self._applescript.run(PLAY_TRACK, name)

    async def play_playlist(self, name: str) -> str:
        return await self._applescript.run(PLAY_PLAYLIST, name)

    async def control(self, action: str) -> str:
        return await self._applescript.run(CONTROL, action)

    async def mode(self, setting: str, state: str) -> str:
        """Set shuffle or repeat, and answer with the position it is now in."""
        return await self._applescript.run(MODE, setting, state)

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
