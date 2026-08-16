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
import contextlib
import json
import os
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiohttp import web

from ev.application.confirmation import ConfirmationRequest, satisfiable
from ev.domain.access import AccessLevel
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
ABANDONED_AFTER = 120.0
"""How long a turn waits for an answer it was promised. A page that closed
mid-question must not park a turn forever, and a turn nobody answers is
declined -- silence is not consent here either."""

Handler = Callable[..., Awaitable[ToolResult | Clarification | None]]
Looker = Callable[[bytes, str | None, str | None], Awaitable[Any]]
"""A frame, what was said while looking, and the locale. The browser owns the
camera here, the same way it owns the microphone: `getUserMedia` asks in the
browser's name, and E.V. does not pretend to hold a permission it was not
given."""

Transcriber = Callable[[Path, str], Awaitable[str]]
History = Callable[[int, int | None, str | None], Awaitable[list[JournalEntry]]]
NowPlaying = Callable[[], Awaitable[dict[str, object] | None]]
"""What Music is on, for the player widget. A read that fills a view, so it is
a GET and never a turn -- null when nothing is playing."""


def _asking(request: ConfirmationRequest) -> dict[str, Any]:
    """A question, as the page receives it. The application and the assurance
    travel with it: the page decides what it can answer, and what to offer."""
    return {
        "outcome": "confirm",
        "tool": request.tool,
        "risk": request.risk.value,
        "arguments": dict(request.arguments),
        "application": request.application,
        "assurance": request.assurance.value,
    }


def _outcome(result: ToolResult | Clarification | None) -> dict[str, Any]:
    if result is None:
        return {"outcome": "not_understood"}
    if isinstance(result, Clarification):
        return {"outcome": "unsure", **json.loads(result.model_dump_json())}
    return {"outcome": "ran", **json.loads(result.model_dump_json())}


class Asked:
    """One turn, parked mid-way because it needs an answer.

    HTTP has no way to hold a question open and keep talking, so the turn runs
    as a task: `/api/turn` returns either its outcome or its first question,
    and `/api/confirm` resumes it. The turn itself is unaware -- it is awaiting
    a confirmation port exactly as it does on the socket.
    """

    def __init__(self, task: asyncio.Task[Any]) -> None:
        self.task = task
        self.questions: asyncio.Queue[ConfirmationRequest] = asyncio.Queue()
        self.answers: asyncio.Queue[bool] = asyncio.Queue()
        self.asked: ConfirmationRequest | None = None
        """The question waiting to be answered, so an answer that also sets a
        level can only set it for the application that was asked about."""

    verifies = False
    """A page cannot raise macOS's authentication: `getUserMedia` asks in the
    browser's name and there is no equivalent for the owner's password. An
    application set to `verify` is answered in the app or not at all."""

    async def confirm(self, request: ConfirmationRequest) -> bool:
        if not satisfiable(request, self):
            return False
        self.asked = request
        await self.questions.put(request)
        try:
            return await asyncio.wait_for(self.answers.get(), ABANDONED_AFTER)
        except (TimeoutError, asyncio.CancelledError):
            return False

    async def next_step(self) -> dict[str, Any]:
        """Whichever comes first: a question, or the end of the turn."""
        question = asyncio.ensure_future(self.questions.get())
        done, _ = await asyncio.wait(
            {question, self.task}, return_when=asyncio.FIRST_COMPLETED
        )

        if question in done:
            return _asking(question.result())

        question.cancel()
        return _outcome(self.task.result())


class WebSurface:
    def __init__(
        self,
        *,
        state_dir: Path,
        handle: Handler,
        history: History | None = None,
        now_playing: NowPlaying | None = None,
        transcribe: Transcriber | None = None,
        look: Looker | None = None,
        remember: Callable[[str, AccessLevel], None] | None = None,
        assets: Path | None = None,
        port: int = DEFAULT_PORT,
        confirmation: Any | None = None,
        turn_lock: asyncio.Lock | None = None,
    ) -> None:
        self._state_dir = state_dir
        self._handle = handle
        # Shared with the socket: one core, one turn at a time, one person
        # being asked.
        self._confirmation = confirmation
        self._history = history
        self._now_playing = now_playing
        self._transcribe = transcribe
        self._look = look
        self._remember_level = remember
        self._assets = assets
        self._port = port
        self._token = ""
        self._turn = turn_lock or asyncio.Lock()
        self._parked: Asked | None = None
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
        app.router.add_post("/api/confirm", self._confirm_route)
        app.router.add_post("/api/audio", self._audio_route)
        app.router.add_post("/api/vision", self._vision_route)
        app.router.add_get("/api/history", self._history_route)
        app.router.add_get("/api/now-playing", self._now_playing_route)

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

        return web.json_response(await self._begin(text, body.get("locale")))

    async def _begin(self, text: str, locale: str | None = None) -> dict[str, Any]:
        """Run a turn until it finishes or asks something."""
        return await self._start(lambda: self._handle(text, locale))

    async def _start(self, turn: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
        """A turn, whatever started it: typed, spoken, or looked at.

        Taken as a thunk rather than a coroutine so that nothing is created
        until the lock is held -- a coroutine built and then abandoned because
        the lock raised is a coroutine nobody awaits.
        """
        await self._abandon()
        await self._turn.acquire()

        parked = Asked(asyncio.ensure_future(turn()))
        self._parked = parked
        if self._confirmation is not None:
            self._confirmation.bind(parked)

        step = await parked.next_step()
        if step["outcome"] != "confirm":
            self._release()
        return step

    async def _vision_route(self, request: web.Request) -> web.StreamResponse:
        """One frame, one turn, nothing written down.

        The audio route writes a temporary file because whisper reads a path.
        A vision model takes bytes, so a frame is decoded here, answered, and
        gone -- invariant 8, and the shortest possible life for a picture of
        someone's room.
        """
        look = self._look
        if look is None:
            raise web.HTTPServiceUnavailable(text="this daemon cannot see")

        body = await request.json()
        try:
            image = base64.b64decode(str(body.get("image", "")), validate=True)
        except (ValueError, binascii.Error):
            raise web.HTTPBadRequest(text="the image is not valid base64") from None

        if not image:
            raise web.HTTPBadRequest(text="there is no frame here")

        text = str(body.get("text") or "").strip() or None
        locale = body.get("locale")

        return web.json_response(await self._start(lambda: look(image, text, locale)))

    async def _confirm_route(self, request: web.Request) -> web.StreamResponse:
        parked = self._parked
        if parked is None:
            raise web.HTTPConflict(text="nothing is waiting on an answer")

        body = await request.json()
        level = body.get("remember")
        # "Always" and "never" are answers about the application, not about
        # this call, and the application comes from the question -- never from
        # the answer, which is the shape of every confused-deputy bug there is.
        if (
            level is not None
            and parked.asked is not None
            and parked.asked.application
            and self._remember_level is not None
        ):
            self._remember_level(parked.asked.application, AccessLevel(str(level)))
        await parked.answers.put(bool(body.get("granted")))

        step = await parked.next_step()
        if step["outcome"] != "confirm":
            self._release()
        return web.json_response(step)

    def _release(self) -> None:
        if self._confirmation is not None:
            self._confirmation.bind(None)
        self._parked = None
        if self._turn.locked():
            self._turn.release()

    async def _abandon(self) -> None:
        """A previous turn still waiting on an answer nobody gave.

        Cancelling it declines the question, which is the same answer a closed
        socket and an empty pipe get.
        """
        parked = self._parked
        if parked is None:
            return

        parked.task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await parked.task
        self._release()

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

        return web.json_response({"heard": said, **await self._begin(said, locale)})

    async def _history_route(self, request: web.Request) -> web.StreamResponse:
        if self._history is None:
            raise web.HTTPServiceUnavailable(text="this daemon keeps no journal")

        try:
            limit = int(request.query.get("limit", "20"))
        except ValueError:
            limit = 20

        # `q` searches, its absence pages. An empty `q=` is someone who
        # cleared the box, which is the whole trail rather than nothing.
        query = request.query.get("q") or None
        entries = await self._history(max(1, min(limit, 500)), None, query)
        return web.json_response(
            {"entries": [json.loads(entry.model_dump_json()) for entry in entries]}
        )

    async def _now_playing_route(self, request: web.Request) -> web.StreamResponse:
        # A daemon without the read answers "nothing playing" rather than an
        # error: the widget draws a resting player either way, and a 503 would
        # only fill its console with a fault it cannot act on.
        if self._now_playing is None:
            return web.json_response(None)
        return web.json_response(await self._now_playing())
