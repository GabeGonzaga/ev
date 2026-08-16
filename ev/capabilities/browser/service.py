"""Orchestration. Never touches the system directly.

Thin, deliberately: permissions, confirmation and journalling belong to
`Registry.call()` (invariant 4), so what is left here is composing the result
and the line E.V. says back. Capabilities that must resolve a name against the
real world -- shortcuts, music -- will carry more.
"""

from __future__ import annotations

from ev.application.speech import Speaker
from ev.capabilities.browser.adapters import OpenAdapter
from ev.capabilities.browser.args import OpenUrlArgs
from ev.domain.results import ToolResult

OPEN_URL = "browser.open_url"

SMALL = (900, 60, 1420, 700)
"""Where a small window goes: up the right-hand side, widget-shaped. Off to
one side because the point of asking for a window rather than a tab is to have
it beside something else."""


class BrowserService:
    def __init__(self, adapter: OpenAdapter, speaker: Speaker | None = None) -> None:
        self._adapter = adapter
        self._speaker = speaker or Speaker()

    async def open_url(self, args: OpenUrlArgs) -> ToolResult:
        url = str(args.url)

        # A window if one was asked for and the browser can be told; a tab
        # otherwise. The fallback is silent on purpose -- the page opened, and
        # which shape of window it landed in is not worth a sentence.
        windowed = args.where == "window" and await self._adapter.open_small(url, SMALL)
        if not windowed:
            await self._adapter.open_url(url)

        # The host, not the URL: this is read aloud, and a full URL is not
        # something anyone wants spoken.
        return ToolResult.success(
            OPEN_URL,
            data={"url": url, "where": "window" if windowed else "tab"},
            speech=self._speaker.say("browser.opening", host=args.url.host),
        )
