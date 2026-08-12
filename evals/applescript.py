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
* step moves the volume by zero, so the arithmetic and the clamping run

Needs a Mac with Music installed, so it lives beside `make eval` rather than
in the suite.
"""

from __future__ import annotations

import asyncio
import sys

from ev.capabilities.music.adapters import QUEUE, MusicAdapter
from ev.infrastructure.macos.applescript import AppleScriptClient, AppleScriptError
from ev.infrastructure.macos.processes import ProcessRunner

MISSING = "EV Nonexistent QQQ"


async def main() -> int:
    adapter = MusicAdapter(AppleScriptClient(ProcessRunner()))
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
    await expect_error(
        "play album", adapter.play_album(MISSING), "nothing in the library matches"
    )
    await expect_error(
        "play track", adapter.play_track(MISSING), "nothing in the library matches"
    )
    await expect_error(
        "play playlist", adapter.play_playlist(MISSING), "there is no playlist"
    )
    # No branch matches, so this reads the player and changes nothing.
    await expect_value("control", adapter.control("noop"))
    await expect_value("volume step", adapter.step(0))

    if failures:
        print("\n".join(f"  FAILED {failure}" for failure in failures), file=sys.stderr)
        return 1

    print("every script runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
