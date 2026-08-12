"""The local web surface: the same E.V., in this machine's browser.

The weakest of the three doors, and the one written most carefully. It adds
nothing to what E.V. can do -- every request ends at `Registry.call()`, the
same door the panel and the CLI reach through -- and it adds a way in that did
not exist before, which is why `security.py` exists and is tested.

Off unless asked for. Loopback only. Token on every request.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiohttp import web

from ev.domain.journal import JournalEntry
from ev.domain.results import Clarification, ToolResult
from ev.infrastructure.web.security import (
    issue,
    local_host,
    matches,
    same_origin,
    token_path,
)

DEFAULT_PORT = 8765
LOOPBACK = "127.0.0.1"

Handler = Callable[[str], Awaitable[ToolResult | Clarification | None]]
Transcriber = Callable[[Path, str], Awaitable[str]]
History = Callable[[int, int | None], Awaitable[list[JournalEntry]]]


def _outcome(result: ToolResult | Clarification | None) -> dict[str, Any]:
    if result is None:
        return {"outcome": "not_understood"}
    if isinstance(result, Clarification):
        return {"outcome": "unsure", **json.loads(result.model_dump_json())}
    return {"outcome": "ran", **json.loads(result.model_dump_json())}


class WebSurface:
    def __init__(
        self,
        *,
        state_dir: Path,
        handle: Handler,
        history: History | None = None,
        transcribe: Transcriber | None = None,
        assets: Path | None = None,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._state_dir = state_dir
        self._handle = handle
        self._history = history
        self._transcribe = transcribe
        self._assets = assets
        self._port = port
        self._token = ""
        self._turn = asyncio.Lock()
        self._runner: web.AppRunner | None = None

    @property
    def token(self) -> str:
        return self._token

    def url(self) -> str:
        # The token rides in the fragment, which browsers never send to a
        # server and never write to a Referer header. The page reads it once
        # and drops it from the address bar.
        return f"http://{LOOPBACK}:{self._port}/#token={self._token}"

    async def start(self) -> None:
        self._token = issue(self._state_dir)

        app = web.Application(middlewares=[self._guard])
        app.router.add_post("/api/turn", self._turn_route)
        app.router.add_post("/api/audio", self._audio_route)
        app.router.add_get("/api/history", self._history_route)

        if self._assets is not None and self._assets.is_dir():
            app.router.add_get("/", self._index)
            app.router.add_static("/assets", self._assets / "assets")

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        # Loopback, explicitly. Binding 0.0.0.0 is the defect CLAUDE.md names.
        site = web.TCPSite(self._runner, LOOPBACK, self._port)
        await site.start()

    async def aclose(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
        # The token dies with the run that issued it.
        token_path(self._state_dir).unlink(missing_ok=True)

    @web.middleware
    async def _guard(
        self,
        request: web.Request,
        handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
    ) -> web.StreamResponse:
        if not local_host(request.headers.get("Host"), self._port):
            # A hostile site pointing its own name at 127.0.0.1 still sends
            # that name here.
            raise web.HTTPForbidden(text="not a loopback host")

        if not same_origin(request.headers.get("Origin"), self._port):
            raise web.HTTPForbidden(text="cross-origin")

        if request.path.startswith("/api/"):
            supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
            if not matches(self._token, supplied):
                # No hint about what would have worked.
                raise web.HTTPUnauthorized(text="no")

        return await handler(request)

    async def _index(self, request: web.Request) -> web.StreamResponse:
        assert self._assets is not None
        return web.FileResponse(self._assets / "index.html")

    async def _turn_route(self, request: web.Request) -> web.StreamResponse:
        body = await request.json()
        text = str(body.get("text", "")).strip()
        if not text:
            raise web.HTTPBadRequest(text="nothing to do")

        async with self._turn:
            outcome = await self._handle(text)
        return web.json_response(_outcome(outcome))

    async def _audio_route(self, request: web.Request) -> web.StreamResponse:
        if self._transcribe is None:
            raise web.HTTPServiceUnavailable(text="this daemon cannot transcribe")

        body = await request.json()
        try:
            audio = base64.b64decode(str(body.get("audio", "")), validate=True)
        except (ValueError, binascii.Error):
            raise web.HTTPBadRequest(text="audio is not valid base64") from None

        locale = str(body.get("locale") or "en")

        handle, name = tempfile.mkstemp(prefix="ev-web-", suffix=".wav")
        path = Path(name)
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(audio)
            said = await self._transcribe(path, locale)
        except Exception as error:
            raise web.HTTPBadRequest(text=str(error)) from error
        finally:
            # A recording of someone's voice does not outlive the sentence.
            path.unlink(missing_ok=True)

        async with self._turn:
            outcome = await self._handle(said)

        return web.json_response({"heard": said, **_outcome(outcome)})

    async def _history_route(self, request: web.Request) -> web.StreamResponse:
        if self._history is None:
            raise web.HTTPServiceUnavailable(text="this daemon keeps no journal")

        try:
            limit = int(request.query.get("limit", "20"))
        except ValueError:
            limit = 20

        entries = await self._history(max(1, min(limit, 500)), None)
        return web.json_response(
            {"entries": [json.loads(entry.model_dump_json()) for entry in entries]}
        )
