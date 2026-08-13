"""What is actually installed.

A spoken application name is matched against this and never passed through.
`CLAUDE.md` states the rule for shortcuts -- "resolved against the real list,
never passed through freely" -- and it is the same rule here for the same
reason: `open -a` will happily launch something the user did not mean, and the
model is the one supplying the name.

Reading a directory is not "probing the system for permission state" (invariant
7): it is a list of folders, the same one the Dock reads.
"""

from __future__ import annotations

from pathlib import Path

WHERE = (
    Path("/Applications"),
    Path("/Applications/Utilities"),
    Path("/System/Applications"),
    Path("/System/Applications/Utilities"),
    Path.home() / "Applications",
)
"""Where macOS keeps applications. Not `/System/Library/CoreServices`, which
holds things that are not applications people ask for by name."""

SUFFIX = ".app"


class Applications:
    """The installed applications, by name."""

    def __init__(self, where: tuple[Path, ...] = WHERE) -> None:
        self._where = where

    def installed(self) -> list[str]:
        found: set[str] = set()
        for directory in self._where:
            try:
                entries = sorted(directory.iterdir())
            except OSError:
                # A directory that does not exist, or one macOS will not let
                # this process read, is not an error: it is one place out of
                # five with nothing to contribute.
                continue
            found.update(
                entry.name.removesuffix(SUFFIX)
                for entry in entries
                if entry.name.endswith(SUFFIX)
            )
        return sorted(found)
