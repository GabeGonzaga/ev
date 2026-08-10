"""Orchestration. Never touches the system directly.

Thin, deliberately: permissions, confirmation and journalling belong to
`Registry.call()` (invariant 4), so what is left here is composing the result
and the line E.V. says back. Capabilities that must resolve a name against the
real world -- shortcuts, music -- will carry more.
"""

from __future__ import annotations

from ev.capabilities.browser.adapters import OpenAdapter
from ev.capabilities.browser.args import OpenUrlArgs
from ev.domain.results import ToolResult

OPEN_URL = "browser.open_url"


class BrowserService:
    def __init__(self, adapter: OpenAdapter) -> None:
        self._adapter = adapter

    async def open_url(self, args: OpenUrlArgs) -> ToolResult:
        url = str(args.url)
        await self._adapter.open_url(url)

        # The host, not the URL: this is read aloud, and a full URL is not
        # something anyone wants spoken.
        return ToolResult.success(
            OPEN_URL, data={"url": url}, speech=f"Opening {args.url.host}"
        )
