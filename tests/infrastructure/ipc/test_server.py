"""The daemon, over a real Unix socket.

No mocked transport here: a socket file, its mode bits and its framing are the
things most likely to be wrong, and none of them survive being faked. This runs
on Linux, which is where CI is.
"""

from __future__ import annotations

import asyncio
import json
import stat
import tempfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest

from ev.application.confirmation import ConfirmationRequest
from ev.domain.results import Clarification, ToolErrorCode, ToolResult
from ev.domain.risk import RiskLevel
from ev.infrastructure.ipc.client import DaemonRefused, DaemonUnavailable, IpcClient
from ev.infrastructure.ipc.server import (
    IpcServer,
    SessionConfirmation,
    socket_path,
)
from protocol.messages import PROTOCOL_VERSION, Hello, Request, UtteranceSubmit

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

    async def handle(self, utterance: str) -> ToolResult | Clarification | None:
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
        async def handle(self, utterance: str) -> ToolResult | Clarification | None:
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
        with pytest.raises(DaemonRefused, match=r"speaks 1\.0"):
            async with IpcClient(socket_path(state), protocol="0.9"):
                pass
        break
