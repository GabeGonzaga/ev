"""The daemon: one warm core, several clients, over a Unix socket.

A socket rather than a port, because a port is reachable by every process on
the machine including a browser tab. Mode 0600, so it is reachable by this user
and nobody else. Newline-delimited JSON, one message per line.

The reason this exists at all is the model. A cold load measured 7.46 s against
0.40 s warm, so a core that dies with its UI pays that on every restart. This
one outlives its clients.

Turns are serialised. A voice assistant does one thing at a time, and the
alternative -- two utterances interleaving through one registry, one journal
and one confirmation surface -- is a race with a user's machine at the end of
it.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import os
import socket
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from pydantic import ValidationError

from ev.application.confirmation import ConfirmationRequest
from ev.domain.results import Clarification, ToolResult
from protocol.messages import (
    PROTOCOL_VERSION,
    AudioSubmit,
    ConfirmationRequired,
    ConfirmationRespond,
    Event,
    Hello,
    Request,
    Response,
    ResponseError,
    SessionCancel,
    SpeechRequested,
    StateChanged,
    ToolCompleted,
    TranscriptionPartial,
    UtteranceSubmit,
)

SOCKET_FILE = "ev.sock"
SUN_PATH_MAX = 100
"""Under the 104 bytes macOS allows and the 108 Linux does, with room for the
trailing NUL. `~/Library/Application Support/EV/ev.sock` is comfortably inside
it; a deeply nested home directory is not, and that failure deserves a sentence
naming the path rather than the kernel's bare EINVAL."""
MAX_LINE = 12 * 1024 * 1024
"""asyncio caps a line at 64 KiB by default, and audio does not fit in that:
~2.5 seconds of speech is a ~104 KB line, which killed the connection with
"chunk exceed the limit" and no explanation. This is the protocol's audio bound
with room for the JSON around it."""

CLOSE_TIMEOUT = 2.0
"""A backstop on shutdown. Connections are closed first, so this should never
be reached; if it is, exiting matters more than exiting tidily."""

CONFIRMATION_TIMEOUT = 120.0
"""A person is being asked a question. Long, but not forever: a client that
vanished mid-confirmation must not pin a turn open."""


def socket_path(state_dir: Path) -> Path:
    return state_dir / SOCKET_FILE


class Session:
    """One connected client. Owns its writer and its pending confirmations."""

    def __init__(
        self, writer: asyncio.StreamWriter, *, timeout: float = CONFIRMATION_TIMEOUT
    ) -> None:
        self._writer = writer
        self._timeout = timeout
        self._pending: dict[str, asyncio.Future[bool]] = {}
        self.greeted = False

    async def emit(self, event: Event) -> None:
        self._writer.write(event.model_dump_json().encode() + b"\n")
        await self._writer.drain()

    async def send(self, response: Response) -> None:
        self._writer.write(response.model_dump_json().encode() + b"\n")
        await self._writer.drain()

    async def confirm(self, request: ConfirmationRequest) -> bool:
        identifier = uuid.uuid4().hex
        waiting: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._pending[identifier] = waiting

        await self.emit(
            ConfirmationRequired(
                id=identifier,
                tool=request.tool,
                risk=request.risk,
                arguments=dict(request.arguments),
            )
        )

        try:
            return await asyncio.wait_for(waiting, self._timeout)
        except (TimeoutError, asyncio.CancelledError):
            # Silence is not consent, here or on a terminal.
            return False
        finally:
            self._pending.pop(identifier, None)

    def answer(self, message: ConfirmationRespond) -> bool:
        waiting = self._pending.get(message.request)
        if waiting is None or waiting.done():
            return False
        waiting.set_result(message.granted)
        return True

    def cancel(self) -> None:
        for waiting in self._pending.values():
            if not waiting.done():
                waiting.set_result(False)


class SessionConfirmation:
    """The registry's confirmation port, pointed at whoever asked.

    The registry is built once and lives as long as the daemon; the person to
    ask changes per turn. Turns are serialised, so one binding at a time is
    enough. Unbound, it declines -- nobody is there to answer.
    """

    def __init__(self) -> None:
        self._session: Session | None = None

    def bind(self, session: Session | None) -> None:
        self._session = session

    async def confirm(self, request: ConfirmationRequest) -> bool:
        if self._session is None:
            return False
        return await self._session.confirm(request)


Handler = Callable[[str], Awaitable[ToolResult | Clarification | None]]
Transcriber = Callable[[Path, str], Awaitable[str]]
"""Audio in, words out. The daemon holds one; what implements it is
`SpeechRecognizer`, and the daemon never learns which engine that is."""


class IpcServer:
    def __init__(
        self,
        *,
        path: Path,
        handle: Handler,
        confirmation: SessionConfirmation,
        transcribe: Transcriber | None = None,
        on_close: Callable[[], Awaitable[None]] | None = None,
        confirmation_timeout: float = CONFIRMATION_TIMEOUT,
    ) -> None:
        self._path = path
        self._handle = handle
        self._transcribe = transcribe
        self._confirmation = confirmation
        self._on_close = on_close
        self._confirmation_timeout = confirmation_timeout
        self._turn = asyncio.Lock()
        self._server: asyncio.AbstractServer | None = None
        self._connections: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        self._guard_length()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._clear_stale()

        self._server = await asyncio.start_unix_server(
            self._connection, path=str(self._path), limit=MAX_LINE
        )
        # Bind first, then narrow: there is a moment where the socket exists
        # with the process umask, and chmod closes it immediately.
        os.chmod(self._path, 0o600)

    def _guard_length(self) -> None:
        # sockaddr_un.sun_path is 104 bytes on macOS, 108 on Linux, and the
        # kernel's own error for exceeding it says nothing about which path.
        encoded = len(str(self._path).encode())
        if encoded > SUN_PATH_MAX:
            raise OSError(
                f"socket path is {encoded} bytes, over the {SUN_PATH_MAX} the "
                f"kernel allows: {self._path}"
            )

    def _clear_stale(self) -> None:
        if not self._path.exists():
            return

        try:
            # A live daemon answers. If nothing does, the file is debris from a
            # process that did not exit cleanly, and unlinking it is the only
            # way a crashed daemon does not need manual cleanup.
            with contextlib.closing(
                socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            ) as probe:
                probe.connect(str(self._path))
        except OSError:
            self._path.unlink()
        else:
            raise OSError(f"a daemon is already listening on {self._path}")

    async def serve_forever(self) -> None:
        if self._server is None:
            await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def aclose(self) -> None:
        if self._server is not None:
            self._server.close()

            # Every connected client is closed first. Since 3.12,
            # `wait_closed()` waits for open connections as well as for the
            # listener, so a daemon with a client attached -- which is the
            # normal state, and will be the permanent state once a UI exists --
            # would never finish shutting down. It would hang on SIGTERM and
            # take the unflushed journal with it.
            for writer in list(self._connections):
                writer.close()

            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._server.wait_closed(), CLOSE_TIMEOUT)

        self._path.unlink(missing_ok=True)
        if self._on_close is not None:
            await self._on_close()

    async def _connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        session = Session(writer, timeout=self._confirmation_timeout)
        self._connections.add(writer)
        # Each line is handled in its own task, and this matters: a turn
        # awaiting a confirmation is blocked inside one of them, and the answer
        # arrives on the next line. Handling lines in sequence would mean the
        # reply could only be read after the turn it replies to had finished --
        # a deadlock that ends in the confirmation timing out and declining.
        working: set[asyncio.Task[None]] = set()

        try:
            while line := await reader.readline():
                task = asyncio.create_task(self._line(session, line))
                working.add(task)
                task.add_done_callback(working.discard)
        except ValueError:
            # A line past MAX_LINE. The stream cannot be resynchronised -- the
            # rest of that line is still coming -- so this connection ends, but
            # it ends with a reason rather than in silence.
            with contextlib.suppress(ConnectionError, OSError):
                await self._refuse(
                    session, "", "too_large", f"a message exceeded {MAX_LINE} bytes"
                )
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            # The client is gone. Anything still waiting for it gets a no.
            session.cancel()
            for task in list(working):
                task.cancel()
            self._connections.discard(writer)
            writer.close()
            with contextlib.suppress(ConnectionError, OSError):
                await writer.wait_closed()

    async def _line(self, session: Session, line: bytes) -> None:
        try:
            request = Request.model_validate_json(line)
        except ValidationError as error:
            # No id to answer to, so this cannot be correlated. Report it on a
            # response with an empty id rather than dropping it silently.
            await session.send(
                Response(
                    id="",
                    ok=False,
                    error=ResponseError(code="malformed", message=str(error)[:400]),
                )
            )
            return

        command = request.command

        if isinstance(command, Hello):
            await self._hello(session, request.id, command)
            return

        if not session.greeted:
            await self._refuse(
                session, request.id, "not_greeted", "send hello before anything else"
            )
            return

        if isinstance(command, ConfirmationRespond):
            answered = session.answer(command)
            await session.send(
                Response(id=request.id, ok=answered, payload={"answered": answered})
            )
            return

        if isinstance(command, SessionCancel):
            session.cancel()
            await session.send(Response(id=request.id, ok=True))
            return

        if isinstance(command, AudioSubmit):
            await self._audio(session, request.id, command)
            return

        if isinstance(command, UtteranceSubmit):
            await self._utterance(session, request.id, command)

    async def _audio(
        self, session: Session, request_id: str, command: AudioSubmit
    ) -> None:
        """Transcribe, say what was heard, then take the turn.

        The audio reaches disk for as long as whisper needs a file to read and
        no longer: it is written to a private temporary file and deleted in a
        finally, because a recording of someone's voice is not something to
        leave lying around after the sentence has been understood.
        """
        if self._transcribe is None:
            await self._refuse(
                session, request_id, "no_recognizer", "this daemon cannot transcribe"
            )
            return

        try:
            audio = base64.b64decode(command.audio, validate=True)
        except (ValueError, binascii.Error):
            await self._refuse(
                session, request_id, "malformed_audio", "audio is not valid base64"
            )
            return

        handle, name = tempfile.mkstemp(prefix="ev-", suffix=".wav")
        path = Path(name)
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(audio)

            try:
                said = await self._transcribe(path, command.locale or "en")
            except Exception as error:
                await self._refuse(
                    session, request_id, "transcription_failed", str(error)
                )
                return
        finally:
            path.unlink(missing_ok=True)

        # What E.V. heard, before it acts on it. A user who is misheard should
        # see it in the words, not infer it from the wrong action.
        await session.emit(TranscriptionPartial(text=said))

        await self._utterance(
            session,
            request_id,
            UtteranceSubmit(text=said, locale=command.locale),
        )

    async def _hello(self, session: Session, request_id: str, hello: Hello) -> None:
        if hello.protocol != PROTOCOL_VERSION:
            # Refuse rather than degrade: a version we do not know is a
            # conversation neither side can hold.
            await self._refuse(
                session,
                request_id,
                "protocol_mismatch",
                f"this daemon speaks {PROTOCOL_VERSION}, you speak {hello.protocol}",
            )
            return

        session.greeted = True
        await session.send(
            Response(id=request_id, ok=True, payload={"protocol": PROTOCOL_VERSION})
        )

    async def _refuse(
        self, session: Session, request_id: str, code: str, message: str
    ) -> None:
        await session.send(
            Response(
                id=request_id,
                ok=False,
                error=ResponseError(code=code, message=message),
            )
        )

    async def _utterance(
        self, session: Session, request_id: str, command: UtteranceSubmit
    ) -> None:
        async with self._turn:
            self._confirmation.bind(session)
            try:
                outcome = await self._handle(command.text)
            except Exception as error:  # the daemon outlives one bad turn
                await self._refuse(
                    session,
                    request_id,
                    "turn_failed",
                    f"{type(error).__name__}: {error}",
                )
                return
            finally:
                self._confirmation.bind(None)

        await self._announce(session, command, outcome)
        await session.send(Response(id=request_id, ok=True, payload=_payload(outcome)))

    async def _announce(
        self,
        session: Session,
        command: UtteranceSubmit,
        outcome: ToolResult | Clarification | None,
    ) -> None:
        """What happened, as events, before the response that closes the turn.

        The response is for the client that asked; the events are what a UI
        renders and what speaks. Speech crosses as intent -- a sentence and a
        voice -- because the audio device belongs to the native layer.
        """
        spoken: str | None = None

        if isinstance(outcome, ToolResult):
            await session.emit(
                ToolCompleted(
                    tool=outcome.tool,
                    ok=outcome.ok,
                    speech=outcome.speech,
                    error=outcome.error.message if outcome.error else None,
                )
            )
            spoken = outcome.speech or (
                outcome.error.message if outcome.error else None
            )
        elif isinstance(outcome, Clarification):
            spoken = outcome.response

        if spoken:
            await session.emit(
                SpeechRequested(text=spoken, voice=command.locale or "en")
            )

        await session.emit(StateChanged(state="idle"))


def _payload(outcome: ToolResult | Clarification | None) -> dict[str, object]:
    if outcome is None:
        return {"outcome": "not_understood"}
    if isinstance(outcome, Clarification):
        return {"outcome": "unsure", **json.loads(outcome.model_dump_json())}
    return {"outcome": "ran", **json.loads(outcome.model_dump_json())}
