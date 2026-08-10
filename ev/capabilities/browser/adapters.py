"""The boundary. The only code in this capability that talks to macOS."""

from __future__ import annotations

from ev.infrastructure.macos.processes import ProcessRunner

OPEN_TIMEOUT = 10.0


class OpenAdapter:
    """`open(1)`: hand a URL to whatever the user set as their default browser."""

    def __init__(self, processes: ProcessRunner) -> None:
        self._processes = processes

    async def open_url(self, url: str) -> None:
        # "--" ends option parsing, so a URL that starts with "-" is a URL and
        # not a flag. The adapter owns every element of this list.
        await self._processes.run(["open", "--", url], timeout=OPEN_TIMEOUT)
