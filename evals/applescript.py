"""`make applescript`: run every AppleScript, not just compile it.

`osacompile` proves the syntax parses and the terminology resolves. It does
not prove the script works: `set text item delimiters` inside a
`tell application "Music"` block compiles perfectly and fails at runtime with
"Music got an error", because that property belongs to AppleScript and not to
Music. That shipped, and a user found it.

So each script is run here on a path with no side effect:

* album, track and playlist are asked for a name that cannot exist, so they
  fail in their own words after reaching the library
* control is given an action matching no branch, so it only reads the player
* the switch script is given a setting matching no branch, so shuffle and
  repeat are left exactly as the user set them
* step moves the volume by zero, so the arithmetic and the clamping run
* the note is asked for a folder that cannot exist, and the reminder for a
  list that cannot exist, so both fail before they make anything

Needs a Mac with Music, Notes and Reminders installed, so it lives beside
`make eval` rather than in the suite. It sends Apple Events to each of them, so
macOS asks for permission the first time.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime

from ev.capabilities.music.adapters import QUEUE, MusicAdapter
from ev.capabilities.notes.adapters import NotesAdapter
from ev.capabilities.reminders.adapters import RemindersAdapter
from ev.infrastructure.macos.applescript import AppleScriptClient, AppleScriptError
from ev.infrastructure.macos.processes import ProcessRunner

MISSING = "EV Nonexistent QQQ"


async def main() -> int:
    applescript = AppleScriptClient(ProcessRunner())
    adapter = MusicAdapter(applescript)
    notes = NotesAdapter(applescript)
    reminders = RemindersAdapter(applescript)
    failures: list[str] = []

    async def expect_error(name: str, run: object, wanted: str) -> None:
        try:
            await run  # type: ignore[misc]
        except AppleScriptError as error:
            if wanted in str(error):
                print(f"  {name:<16} fails in its own words")
                return
            failures.append(f"{name}: unexpected error: {error}")
            return
        failures.append(f"{name}: expected an error and got none")

    async def expect_value(name: str, run: object) -> None:
        try:
            answer = await run  # type: ignore[misc]
        except AppleScriptError as error:
            failures.append(f"{name}: {error}")
            return
        print(f"  {name:<16} answered {answer!r}")

    print(f"running every music script against Music (queue: {QUEUE})")

    await expect_value("list playlists", adapter.playlists())
    await expect_value("list albums", adapter.albums())
    await expect_value("list artists", adapter.artists())
    await expect_error(
        "play album", adapter.play_album(MISSING), "nothing in the library matches"
    )
    await expect_error(
        "play track", adapter.play_track(MISSING), "nothing in the library matches"
    )
    await expect_error(
        "play playlist", adapter.play_playlist(MISSING), "there is no playlist"
    )
    await expect_error(
        "play artist", adapter.play_artist(MISSING), "nothing in the library matches"
    )
    # No branch matches, so this reads the player and changes nothing. It also
    # exercises `my nowPlaying()`, which compiled perfectly while being sent
    # to Music -- "Can't continue nowPlaying", found by running it.
    await expect_value("control", adapter.control("noop"))
    # Likewise: no branch matches, so neither switch is written and whatever
    # the user has shuffle and repeat set to survives the check.
    await expect_value("switches", adapter.mode("noop", "toggle"))
    await expect_value("volume step", adapter.step(0))

    print("running every notes script against Notes")

    await expect_value("list folders", notes.folders())
    # The folder cannot exist, so this fails before `make new note` runs.
    await expect_error(
        "create note",
        notes.create(MISSING, "checking", MISSING),
        "there is no folder called",
    )

    print("running every reminders script against Reminders")

    await expect_value("list lists", reminders.lists())
    # The list cannot exist, so this fails before `make new reminder` runs --
    # and it fails after the date has been built, which is the part worth
    # exercising: the arithmetic is in the script.
    await expect_error(
        "create reminder",
        reminders.create(MISSING, datetime(2027, 1, 31, 9, 30), MISSING),
        "there is no list called",
    )

    if failures:
        print("\n".join(f"  FAILED {failure}" for failure in failures), file=sys.stderr)
        return 1

    print("every script runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
