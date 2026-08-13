"""The daemon, over a real Unix socket.

No mocked transport here: a socket file, its mode bits and its framing are the
things most likely to be wrong, and none of them survive being faked. This runs
on Linux, which is where CI is.
"""

from __future__ import annotations

import asyncio
import base64
import json
import stat
import tempfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest

from ev.application.confirmation import ConfirmationRequest
from ev.domain.permissions import Permission, PermissionState
from ev.domain.results import Clarification, ToolErrorCode, ToolResult
from ev.domain.risk import RiskLevel
from ev.infrastructure.ipc.client import DaemonRefused, DaemonUnavailable, IpcClient
from ev.infrastructure.ipc.server import (
    IpcServer,
    SessionConfirmation,
    socket_path,
)
from protocol.messages import (
    PROTOCOL_VERSION,
    AudioSubmit,
    Hello,
    PermissionReport,
    Request,
    UtteranceSubmit,
    VisionSubmit,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def state() -> Iterator[Path]:
    """A short directory.

    pytest's tmp_path is far past the ~104 bytes a Unix socket path may be, so
    the suite needs its own. The server raises a readable error above that
    limit; here we simply stay under it.
    """
    with tempfile.TemporaryDirectory(prefix="ev", dir="/tmp") as directory:
        yield Path(directory)


class Core:
    """Stands in for the assistant. Records what it was asked."""

    def __init__(
        self,
        outcome: ToolResult | Clarification | None = None,
        *,
        confirm_with: SessionConfirmation | None = None,
    ) -> None:
        self.utterances: list[str] = []
        self._outcome = outcome
        self._confirmation = confirm_with
        self.granted: bool | None = None

    async def handle(
        self, utterance: str, locale: str | None = None
    ) -> ToolResult | Clarification | None:
        self.utterances.append(utterance)
        if self._confirmation is not None:
            self.granted = await self._confirmation.confirm(
                ConfirmationRequest(
                    tool="system.empty_trash",
                    risk=RiskLevel.DESTRUCTIVE,
                    arguments={"count": 3},
                )
            )
            if not self.granted:
                return ToolResult.failure(
                    "system.empty_trash",
                    ToolErrorCode.CONFIRMATION_DECLINED,
                    "user declined",
                )
        return self._outcome


async def start(
    state: Path, core: Core, confirmation: SessionConfirmation | None = None
) -> AsyncIterator[IpcServer]:
    server = IpcServer(
        path=socket_path(state),
        handle=core.handle,
        confirmation=confirmation or SessionConfirmation(),
        # Seconds, not minutes: these tests wait out the timeout on purpose.
        confirmation_timeout=0.3,
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())
    try:
        yield server
    finally:
        task.cancel()
        await server.aclose()


async def raw(path: Path) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    return await asyncio.open_unix_connection(str(path))


async def line(reader: asyncio.StreamReader) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(await reader.readline())
    return parsed


async def write(writer: asyncio.StreamWriter, request: Request) -> None:
    writer.write(request.model_dump_json().encode() + b"\n")
    await writer.drain()


# --- the socket itself ----------------------------------------------------


async def test_the_socket_is_readable_by_this_user_only(state: Path) -> None:
    # A port would be reachable by every process on the machine. This is not a
    # port, and 0600 is the other half of that sentence.
    core = Core()
    async for _ in start(state, core):
        mode = stat.S_IMODE(socket_path(state).stat().st_mode)

        assert mode == 0o600
        break


async def test_a_stale_socket_file_is_replaced(state: Path) -> None:
    # Debris from a daemon that did not exit cleanly. Refusing to start would
    # mean a crash needs manual cleanup before the next launch.
    socket_path(state).write_text("not a socket")
    core = Core()

    async for _ in start(state, core):
        assert socket_path(state).is_socket()
        break


async def test_a_live_socket_is_not_stolen(state: Path) -> None:
    core = Core()
    async for _ in start(state, core):
        second = IpcServer(
            path=socket_path(state),
            handle=core.handle,
            confirmation=SessionConfirmation(),
        )

        with pytest.raises(OSError, match="already listening"):
            await second.start()
        break


async def test_the_socket_is_gone_after_shutdown(state: Path) -> None:
    core = Core()
    async for _ in start(state, core):
        pass

    assert not socket_path(state).exists()


# --- the handshake --------------------------------------------------------


async def test_nothing_is_served_before_hello(state: Path) -> None:
    core = Core(ToolResult.success("browser.open_url"))
    async for _ in start(state, core):
        reader, writer = await raw(socket_path(state))
        await write(writer, Request(id="1", command=UtteranceSubmit(text="hello")))

        answer = await line(reader)

        assert answer["ok"] is False
        assert answer["error"]["code"] == "not_greeted"
        assert core.utterances == []
        writer.close()
        break


async def test_a_version_mismatch_is_refused(state: Path) -> None:
    # Refuse rather than degrade: a protocol neither side agrees on is not a
    # conversation worth having.
    core = Core()
    async for _ in start(state, core):
        reader, writer = await raw(socket_path(state))
        await write(
            writer, Request(id="1", command=Hello(protocol="99.0", client="tests"))
        )

        answer = await line(reader)

        assert answer["ok"] is False
        assert answer["error"]["code"] == "protocol_mismatch"
        assert PROTOCOL_VERSION in answer["error"]["message"]
        writer.close()
        break


async def test_a_malformed_line_is_answered_not_dropped(state: Path) -> None:
    core = Core()
    async for _ in start(state, core):
        reader, writer = await raw(socket_path(state))
        writer.write(b"{not json at all}\n")
        await writer.drain()

        answer = await line(reader)

        assert answer["error"]["code"] == "malformed"
        writer.close()
        break


async def test_the_client_refuses_a_daemon_it_cannot_talk_to(state: Path) -> None:
    with pytest.raises(DaemonUnavailable, match="ev --serve"):
        async with IpcClient(socket_path(state)):
            pass


# --- a turn ---------------------------------------------------------------


async def test_a_turn_returns_its_result_and_its_events(state: Path) -> None:
    core = Core(ToolResult.success("browser.open_url", speech="Opening github.com"))
    async for _ in start(state, core):
        async with IpcClient(socket_path(state)) as client:
            response, events = await client.submit("open github.com", locale="pt-PT")

        assert core.utterances == ["open github.com"]
        assert response["ok"] is True
        assert response["payload"]["outcome"] == "ran"

        kinds = [event["type"] for event in events]
        assert kinds == ["tool.completed", "speech.requested", "state.changed"]
        # Speech crosses as intent: a sentence and a voice, never audio.
        assert events[1]["text"] == "Opening github.com"
        assert events[1]["voice"] == "pt-PT"
        break


async def test_an_unrouted_turn_says_so(state: Path) -> None:
    core = Core(None)
    async for _ in start(state, core):
        async with IpcClient(socket_path(state)) as client:
            response, _ = await client.submit("mumble")

        assert response["payload"]["outcome"] == "not_understood"
        break


async def test_a_failing_turn_does_not_kill_the_daemon(state: Path) -> None:
    class Exploding(Core):
        async def handle(
            self, utterance: str, locale: str | None = None
        ) -> ToolResult | Clarification | None:
            raise RuntimeError("boom")

    core = Exploding()
    async for _ in start(state, core):
        async with IpcClient(socket_path(state)) as client:
            reader, writer = await raw(socket_path(state))
            await write(
                writer,
                Request(id="h", command=Hello(protocol=PROTOCOL_VERSION, client="t")),
            )
            await line(reader)
            await write(writer, Request(id="1", command=UtteranceSubmit(text="x")))
            answer = await line(reader)

            assert answer["error"]["code"] == "turn_failed"

            # Still serving.
            response, _ = await client.submit("x")
            assert response["error"]["code"] == "turn_failed"
        break


# --- confirmation across the boundary -------------------------------------


async def test_a_confirmation_is_asked_and_answered(state: Path) -> None:
    # The round trip that a terminal did with input(): an event out, a command
    # back, and the turn blocked in between.
    confirmation = SessionConfirmation()
    core = Core(ToolResult.success("system.empty_trash"), confirm_with=confirmation)

    async for _ in start(state, core, confirmation):
        asked: list[dict[str, Any]] = []

        def ask(event: dict[str, Any], seen: list[dict[str, Any]] = asked) -> bool:
            seen.append(event)
            return True

        async with IpcClient(socket_path(state)) as client:
            response, _events = await client.submit("empty the trash", ask=ask)

        assert core.granted is True
        assert asked[0]["tool"] == "system.empty_trash"
        assert asked[0]["risk"] == "destructive"
        assert asked[0]["arguments"] == {"count": 3}
        assert response["payload"]["outcome"] == "ran"
        break


async def test_a_declined_confirmation_stops_the_call(state: Path) -> None:
    confirmation = SessionConfirmation()
    core = Core(ToolResult.success("system.empty_trash"), confirm_with=confirmation)

    async for _ in start(state, core, confirmation):
        async with IpcClient(socket_path(state)) as client:
            response, _ = await client.submit(
                "empty the trash", ask=lambda event: False
            )

        assert core.granted is False
        assert response["payload"]["ok"] is False
        break


async def test_shutdown_does_not_wait_for_a_client_to_leave(state: Path) -> None:
    """A daemon with a client attached must still be able to exit.

    Since 3.12 `Server.wait_closed()` waits for open connections too, so this
    hung -- on SIGTERM, in the state that will be permanent once a UI is
    connected, taking the unflushed journal with it. Connections are closed
    first now.
    """
    core = Core(ToolResult.success("browser.open_url"))
    server = IpcServer(
        path=socket_path(state),
        handle=core.handle,
        confirmation=SessionConfirmation(),
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())

    reader, writer = await raw(socket_path(state))
    await write(
        writer, Request(id="h", command=Hello(protocol=PROTOCOL_VERSION, client="t"))
    )
    await line(reader)

    task.cancel()
    # The client is still connected on purpose. Two seconds is the backstop;
    # this should return immediately.
    await asyncio.wait_for(server.aclose(), 5.0)

    assert not socket_path(state).exists()


async def test_a_client_that_never_answers_is_not_consent(state: Path) -> None:
    # The IPC equivalent of a pipe: nobody answered, so nothing runs.
    confirmation = SessionConfirmation()
    core = Core(ToolResult.success("system.empty_trash"), confirm_with=confirmation)

    async for _ in start(state, core, confirmation):
        reader, writer = await raw(socket_path(state))
        await write(
            writer,
            Request(id="h", command=Hello(protocol=PROTOCOL_VERSION, client="t")),
        )
        await line(reader)
        await write(writer, Request(id="1", command=UtteranceSubmit(text="empty it")))

        event = await line(reader)
        assert event["type"] == "confirmation.required"

        # Walk away mid-question. The turn is still blocked on the answer, so
        # it ends when the timeout does -- and a timeout is not a yes.
        writer.close()
        await asyncio.sleep(0.6)

        assert core.granted is False
        break


async def test_an_event_is_never_mistaken_for_a_response(state: Path) -> None:
    """confirmation.required carries an `id` of its own.

    A client correlating on the id alone can read that event as the answer to
    its request. Writing the Rust client is what surfaced it: one
    implementation can be self-consistent about a shape that is not actually
    unambiguous. Both clients now dispatch on the presence of `type`.
    """
    confirmation = SessionConfirmation()
    core = Core(ToolResult.success("system.empty_trash"), confirm_with=confirmation)

    async for _ in start(state, core, confirmation):
        seen: list[str] = []

        def ask(event: dict[str, Any], kinds: list[str] = seen) -> bool:
            kinds.append(str(event["type"]))
            return True

        async with IpcClient(socket_path(state)) as client:
            response, _events = await client.submit("empty it", ask=ask)

        # The event was routed to `ask`, not returned as the turn's answer.
        assert seen == ["confirmation.required"]
        assert response["payload"]["outcome"] == "ran"
        assert "type" not in response
        break


async def test_an_unbound_confirmation_declines() -> None:
    # Nobody is connected to ask. Declining is the only honest answer.
    confirmation = SessionConfirmation()

    granted = await confirmation.confirm(
        ConfirmationRequest(tool="system.empty_trash", risk=RiskLevel.DESTRUCTIVE)
    )

    assert granted is False


async def test_a_refused_handshake_reaches_the_client(state: Path) -> None:
    core = Core()
    async for _ in start(state, core):
        with pytest.raises(DaemonRefused, match=r"speaks 1\.5"):
            async with IpcClient(socket_path(state), protocol="0.9"):
                pass
        break


# --- audio ----------------------------------------------------------------


async def test_audio_is_transcribed_then_routed(state: Path) -> None:
    """The path CLAUDE.md describes: the host captures, the core transcribes.

    What was heard is emitted before the turn runs, because a user who is
    misheard should see it in the words rather than infer it from the wrong
    action happening.
    """
    heard: list[tuple[bytes, str]] = []

    async def transcribe(audio: Path, locale: str) -> str:
        heard.append((audio.read_bytes(), locale))
        return "abre example.com"

    core = Core(ToolResult.success("browser.open_url", speech="Opening example.com"))
    server = IpcServer(
        path=socket_path(state),
        handle=core.handle,
        confirmation=SessionConfirmation(),
        transcribe=transcribe,
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())

    try:
        reader, writer = await raw(socket_path(state))
        await write(
            writer,
            Request(id="h", command=Hello(protocol=PROTOCOL_VERSION, client="t")),
        )
        await line(reader)
        await write(
            writer,
            Request(
                id="1",
                command=AudioSubmit(
                    audio=base64.b64encode(b"RIFF....fake wav").decode(),
                    locale="pt-PT",
                ),
            ),
        )

        first = await line(reader)
        assert first["type"] == "transcription.partial"
        assert first["text"] == "abre example.com"

        assert heard == [(b"RIFF....fake wav", "pt-PT")]
        assert core.utterances == ["abre example.com"]
    finally:
        task.cancel()
        await server.aclose()


async def test_a_frame_reaches_the_turn_that_was_asked_to_look(state: Path) -> None:
    """A frame arrives as a command, from a surface, because somebody pressed
    something. Nothing here fetches one."""
    seen: list[tuple[bytes, str | None, str | None]] = []

    async def look(image: bytes, text: str | None, locale: str | None) -> ToolResult:
        seen.append((image, text, locale))
        return ToolResult.success("vision.look", speech="Uma secretária.")

    core = Core(None)
    server = IpcServer(
        path=socket_path(state),
        handle=core.handle,
        confirmation=SessionConfirmation(),
        look=look,
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())

    try:
        reader, writer = await raw(socket_path(state))
        await write(
            writer,
            Request(id="h", command=Hello(protocol=PROTOCOL_VERSION, client="t")),
        )
        await line(reader)
        await write(
            writer,
            Request(
                id="1",
                command=VisionSubmit(
                    image=base64.b64encode(b"a frame").decode(),
                    text="o que é isto?",
                    locale="pt-PT",
                ),
            ),
        )

        first = await line(reader)
        assert first["type"] == "tool.completed"
        assert first["speech"] == "Uma secretária."

        assert seen == [(b"a frame", "o que é isto?", "pt-PT")]
        # The daemon did not invent a sentence to route.
        assert core.utterances == []
    finally:
        task.cancel()
        await server.aclose()


async def test_a_daemon_with_no_eyes_says_so(state: Path) -> None:
    server = IpcServer(
        path=socket_path(state),
        handle=Core(None).handle,
        confirmation=SessionConfirmation(),
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())

    try:
        async with IpcClient(socket_path(state)) as client:
            answer = await client._send(
                VisionSubmit(image=base64.b64encode(b"a frame").decode())
            )

        assert answer["ok"] is False
        assert answer["error"]["code"] == "no_vision"
    finally:
        task.cancel()
        await server.aclose()


async def test_the_recording_does_not_outlive_the_sentence(state: Path) -> None:
    # A recording of someone's voice is not something to leave on disk after
    # the words have been understood.
    seen: list[Path] = []

    async def transcribe(audio: Path, locale: str) -> str:
        seen.append(audio)
        assert audio.exists()
        return "abre example.com"

    core = Core(ToolResult.success("browser.open_url"))
    server = IpcServer(
        path=socket_path(state),
        handle=core.handle,
        confirmation=SessionConfirmation(),
        transcribe=transcribe,
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())

    try:
        reader, writer = await raw(socket_path(state))
        await write(
            writer,
            Request(id="h", command=Hello(protocol=PROTOCOL_VERSION, client="t")),
        )
        await line(reader)
        await write(
            writer,
            Request(id="1", command=AudioSubmit(audio=base64.b64encode(b"x").decode())),
        )
        await line(reader)
        await line(reader)

        assert seen and not seen[0].exists()
    finally:
        task.cancel()
        await server.aclose()


async def test_audio_larger_than_a_default_stream_line_gets_through(
    state: Path,
) -> None:
    """asyncio caps a line at 64 KiB, and audio does not fit in that.

    ~2.5 seconds of 16 kHz speech is a ~104 KB line. Before the limit was
    raised this killed the connection with "chunk exceed the limit" and no
    explanation -- the daemon looked like it had crashed.
    """
    payload = base64.b64encode(b"RIFF" + b"\0" * 200_000).decode()
    assert len(payload) > 64 * 1024

    async def transcribe(audio: Path, locale: str) -> str:
        return "abre example.com"

    core = Core(ToolResult.success("browser.open_url"))
    server = IpcServer(
        path=socket_path(state),
        handle=core.handle,
        confirmation=SessionConfirmation(),
        transcribe=transcribe,
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())

    try:
        async with IpcClient(socket_path(state)) as client:
            await client._write(
                Request(id="a1", command=AudioSubmit(audio=payload, locale="pt-PT"))
            )
            heard = await client._read()

        assert heard["type"] == "transcription.partial"
        assert core.utterances == ["abre example.com"]
    finally:
        task.cancel()
        await server.aclose()


async def test_audio_that_is_not_base64_is_refused(state: Path) -> None:
    async def transcribe(audio: Path, locale: str) -> str:  # pragma: no cover
        raise AssertionError("nothing should be transcribed")

    core = Core()
    server = IpcServer(
        path=socket_path(state),
        handle=core.handle,
        confirmation=SessionConfirmation(),
        transcribe=transcribe,
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())

    try:
        reader, writer = await raw(socket_path(state))
        await write(
            writer,
            Request(id="h", command=Hello(protocol=PROTOCOL_VERSION, client="t")),
        )
        await line(reader)
        await write(
            writer, Request(id="1", command=AudioSubmit(audio="not base64 at all!!"))
        )

        answer = await line(reader)
        assert answer["error"]["code"] == "malformed_audio"
    finally:
        task.cancel()
        await server.aclose()


async def test_a_daemon_without_a_recognizer_says_so(state: Path) -> None:
    core = Core()
    async for _ in start(state, core):
        reader, writer = await raw(socket_path(state))
        await write(
            writer,
            Request(id="h", command=Hello(protocol=PROTOCOL_VERSION, client="t")),
        )
        await line(reader)
        await write(writer, Request(id="1", command=AudioSubmit(audio="AAAA")))

        answer = await line(reader)
        assert answer["error"]["code"] == "no_recognizer"
        break


async def test_history_is_asked_for_not_pushed(state: Path) -> None:
    """History is a request with an answer, not an event stream.

    The UI asks when it opens a panel; nothing pushes the whole trail at a
    client that did not want it.
    """
    from ev.domain.journal import JournalEntry
    from protocol.messages import HistoryQuery

    async def history(
        limit: int, before: int | None, query: str | None = None
    ) -> list[JournalEntry]:
        return [
            JournalEntry(
                id=2,
                recorded_at="2026-08-11T09:00:00+00:00",
                tool="browser.open_url",
                risk=RiskLevel.SAFE,
                ok=True,
                arguments={"url": "https://a.test"},
                speech="Opening a.test",
            )
        ][:limit]

    core = Core()
    server = IpcServer(
        path=socket_path(state),
        handle=core.handle,
        confirmation=SessionConfirmation(),
        history=history,
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())

    try:
        async with IpcClient(socket_path(state)) as client:
            answer = await client._send(HistoryQuery(limit=5))

        assert answer["ok"] is True
        (entry,) = answer["payload"]["entries"]
        assert entry["tool"] == "browser.open_url"
        assert entry["risk"] == "safe"
        assert entry["speech"] == "Opening a.test"
    finally:
        task.cancel()
        await server.aclose()


async def test_a_daemon_with_no_journal_says_so(state: Path) -> None:
    from protocol.messages import HistoryQuery

    core = Core()
    async for _ in start(state, core):
        async with IpcClient(socket_path(state)) as client:
            answer = await client._send(HistoryQuery())

        assert answer["error"]["code"] == "no_history"
        break


async def test_the_host_reports_what_macos_answered(state: Path) -> None:
    """Invariant 7: the core never infers permission state.

    Only the signed process macOS answered can know whether a camera opened,
    so the report is a command it sends -- not something the core polls, and
    not something it guesses from a failure.
    """
    said: list[tuple[Permission, PermissionState]] = []

    server = IpcServer(
        path=socket_path(state),
        handle=Core(None).handle,
        confirmation=SessionConfirmation(),
        report=lambda permission, permission_state: said.append(
            (permission, permission_state)
        ),
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())

    try:
        async with IpcClient(socket_path(state)) as client:
            answer = await client._send(
                PermissionReport(
                    permission=Permission.CAMERA, state=PermissionState.GRANTED
                )
            )

        assert answer["ok"] is True
        assert said == [(Permission.CAMERA, PermissionState.GRANTED)]
    finally:
        task.cancel()
        await server.aclose()


async def test_a_report_is_not_a_turn(state: Path) -> None:
    # It takes no lock, journals nothing and answers at once. A daemon that
    # went quiet while a permission was reported would stall the app's startup.
    server = IpcServer(
        path=socket_path(state),
        handle=Core(None).handle,
        confirmation=SessionConfirmation(),
    )
    await server.start()
    task = asyncio.create_task(server.serve_forever())

    try:
        async with IpcClient(socket_path(state)) as client:
            answer = await client._send(
                PermissionReport(
                    permission=Permission.MICROPHONE, state=PermissionState.GRANTED
                )
            )

        # No reporter wired: still answered, because a client waiting on a
        # response it will never get is worse than a report going nowhere.
        assert answer["ok"] is True
    finally:
        task.cancel()
        await server.aclose()
