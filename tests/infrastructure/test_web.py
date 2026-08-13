"""The local web surface, and mostly the door rather than the room.

These run against a real socket on a real loopback port, because "we refuse a
forged Host header" is a claim about HTTP, and a fake would only prove that a
fake refuses what it was told to refuse.
"""

from __future__ import annotations

import base64
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol

import httpx
import pytest

from ev.application.confirmation import ConfirmationRequest
from ev.domain.access import AccessLevel, Assurance
from ev.domain.journal import JournalEntry
from ev.domain.results import Clarification, ToolErrorCode, ToolResult
from ev.domain.risk import RiskLevel
from ev.infrastructure.ipc.server import SessionConfirmation
from ev.infrastructure.web.security import local_host, matches, same_origin
from ev.infrastructure.web.server import WebSurface


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class Core:
    def __init__(self, outcome: ToolResult | Clarification | None = None) -> None:
        self.asked: list[str] = []
        self._outcome = outcome

    async def handle(
        self, text: str, locale: str | None = None
    ) -> ToolResult | Clarification | None:
        self.asked.append(text)
        return self._outcome


class Answers(Protocol):
    """Anything that can take a turn. The helper does not care which fake."""

    async def handle(
        self, text: str, locale: str | None = None
    ) -> ToolResult | Clarification | None: ...


@asynccontextmanager
async def surface(
    tmp_path: Path, core: Answers, **extra: object
) -> AsyncIterator[tuple[WebSurface, str]]:
    """A running surface, closed deterministically.

    Not a bare async generator: `async for ... break` leaves it suspended, so
    the close runs whenever the collector gets to it. The first version of
    these tests did that, and the one asserting the token file is deleted
    caught it.
    """
    port = free_port()
    web = WebSurface(
        state_dir=tmp_path,
        handle=core.handle,
        port=port,
        **extra,  # type: ignore[arg-type]
    )
    await web.start()
    try:
        yield web, f"http://127.0.0.1:{port}"
    finally:
        await web.aclose()


def headers(token: str, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", **extra}


# --- the door -------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_request_without_a_token_is_refused(tmp_path: Path) -> None:
    core = Core(ToolResult.success("browser.open_url"))
    async with surface(tmp_path, core) as (_web, base):
        async with httpx.AsyncClient() as client:
            answer = await client.post(f"{base}/api/turn", json={"text": "abre a.test"})

        assert answer.status_code == 401
        # Nothing ran, and the refusal does not describe what would have.
        assert core.asked == []
        assert "token" not in answer.text.lower()


@pytest.mark.asyncio
async def test_a_wrong_token_is_refused(tmp_path: Path) -> None:
    core = Core()
    async with surface(tmp_path, core) as (_web, base):
        async with httpx.AsyncClient() as client:
            answer = await client.post(
                f"{base}/api/turn",
                json={"text": "abre a.test"},
                headers=headers("not-the-token"),
            )

        assert answer.status_code == 401
        assert core.asked == []


@pytest.mark.asyncio
async def test_a_forged_host_is_refused(tmp_path: Path) -> None:
    """DNS rebinding, which is the attack this surface exists inside of.

    A hostile site can resolve its own name to 127.0.0.1 and reach this port.
    The browser still sends that site's name in Host, and that is what fails.
    """
    core = Core()
    async with surface(tmp_path, core) as (web, base):
        async with httpx.AsyncClient() as client:
            answer = await client.post(
                f"{base}/api/turn",
                json={"text": "abre a.test"},
                headers=headers(web.token, Host="evil.example.com"),
            )

        assert answer.status_code == 403
        assert core.asked == []


@pytest.mark.asyncio
async def test_a_cross_origin_request_is_refused(tmp_path: Path) -> None:
    # A page on another origin, with a stolen token, still cannot act.
    core = Core()
    async with surface(tmp_path, core) as (web, base):
        async with httpx.AsyncClient() as client:
            answer = await client.post(
                f"{base}/api/turn",
                json={"text": "abre a.test"},
                headers=headers(web.token, Origin="https://evil.example.com"),
            )

        assert answer.status_code == 403
        assert core.asked == []


@pytest.mark.asyncio
async def test_the_token_file_is_private_and_dies_with_the_run(
    tmp_path: Path,
) -> None:
    core = Core()
    path = tmp_path / "web-token"

    async with surface(tmp_path, core) as (web, _base):
        assert path.exists()
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.read_text() == web.token

    # A token that outlives the process it authorised is a credential nobody
    # remembers granting.
    assert not path.exists()


@pytest.mark.asyncio
async def test_the_token_is_in_the_fragment_not_the_query(tmp_path: Path) -> None:
    # Fragments are never sent to a server and never land in a Referer.
    core = Core()
    async with surface(tmp_path, core) as (web, _base):
        assert f"#token={web.token}" in web.url()
        assert "?token=" not in web.url()


# --- the room -------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_turn_runs_and_returns_its_outcome(tmp_path: Path) -> None:
    core = Core(ToolResult.success("browser.open_url", speech="Opening a.test"))
    async with surface(tmp_path, core) as (web, base):
        async with httpx.AsyncClient() as client:
            answer = await client.post(
                f"{base}/api/turn",
                json={"text": "abre a.test"},
                headers=headers(web.token),
            )

        assert answer.status_code == 200
        body = answer.json()
        assert body["outcome"] == "ran"
        assert body["speech"] == "Opening a.test"
        assert core.asked == ["abre a.test"]


@pytest.mark.asyncio
async def test_an_unrouted_turn_says_so(tmp_path: Path) -> None:
    core = Core(None)
    async with surface(tmp_path, core) as (web, base):
        async with httpx.AsyncClient() as client:
            answer = await client.post(
                f"{base}/api/turn", json={"text": "mumble"}, headers=headers(web.token)
            )

        assert answer.json()["outcome"] == "not_understood"


@pytest.mark.asyncio
async def test_audio_is_transcribed_then_routed(tmp_path: Path) -> None:
    seen: list[Path] = []

    async def transcribe(audio: Path, locale: str) -> str:
        seen.append(audio)
        assert audio.exists()
        return "abre example.com"

    core = Core(ToolResult.success("browser.open_url", speech="Opening it"))
    async with surface(tmp_path, core, transcribe=transcribe) as (web, base):
        async with httpx.AsyncClient() as client:
            answer = await client.post(
                f"{base}/api/audio",
                json={
                    "audio": base64.b64encode(b"RIFFfake").decode(),
                    "locale": "pt-PT",
                },
                headers=headers(web.token),
            )

        body = answer.json()
        assert body["heard"] == "abre example.com"
        assert body["outcome"] == "ran"
        assert core.asked == ["abre example.com"]
        # The recording does not outlive the sentence.
        assert seen and not seen[0].exists()


@pytest.mark.asyncio
async def test_history_is_served(tmp_path: Path) -> None:
    async def history(
        limit: int, before: int | None, query: str | None = None
    ) -> list[JournalEntry]:
        return [
            JournalEntry(
                id=1,
                recorded_at="2026-08-11T09:00:00+00:00",
                tool="music.play",
                risk=RiskLevel.SENSITIVE,
                ok=True,
                speech="Playing Blonde",
            )
        ][:limit]

    core = Core()
    async with surface(tmp_path, core, history=history) as (web, base):
        async with httpx.AsyncClient() as client:
            answer = await client.get(
                f"{base}/api/history?limit=5", headers=headers(web.token)
            )

        (entry,) = answer.json()["entries"]
        assert entry["tool"] == "music.play"
        assert entry["risk"] == "sensitive"


@pytest.mark.asyncio
async def test_a_search_reaches_the_journal(tmp_path: Path) -> None:
    asked: list[str | None] = []

    async def history(
        limit: int, before: int | None, query: str | None = None
    ) -> list[JournalEntry]:
        asked.append(query)
        return []

    core = Core()
    async with (
        surface(tmp_path, core, history=history) as (web, base),
        httpx.AsyncClient() as client,
    ):
        for suffix in ("?q=blonde", "?q=", ""):
            await client.get(f"{base}/api/history{suffix}", headers=headers(web.token))

    # An empty box is the whole trail, not an empty search.
    assert asked == ["blonde", None, None]


@pytest.mark.asyncio
async def test_a_daemon_without_a_recognizer_says_so(tmp_path: Path) -> None:
    core = Core()
    async with surface(tmp_path, core) as (web, base):
        async with httpx.AsyncClient() as client:
            answer = await client.post(
                f"{base}/api/audio",
                json={"audio": base64.b64encode(b"x").decode()},
                headers=headers(web.token),
            )

        assert answer.status_code == 503


# --- the checks on their own ----------------------------------------------


def test_loopback_names_only() -> None:
    assert local_host("127.0.0.1:8765", 8765)
    assert local_host("localhost:8765", 8765)
    assert not local_host("evil.example.com:8765", 8765)
    assert not local_host("127.0.0.1:9999", 8765)
    assert not local_host(None, 8765)


def test_origin_absent_is_allowed_and_foreign_is_not() -> None:
    # A same-origin navigation sends none; a cross-site fetch always does.
    assert same_origin(None, 8765)
    assert same_origin("http://127.0.0.1:8765", 8765)
    assert not same_origin("https://evil.example.com", 8765)
    assert not same_origin("file://", 8765)


def test_token_comparison_does_not_short_circuit() -> None:
    assert matches("abc", "abc")
    assert not matches("abc", "abd")
    assert not matches("abc", "")
    assert not matches("abc", None)


# --- confirmation ---------------------------------------------------------


class Destructive:
    """A core whose turn asks before it acts, the way a destructive tool does."""

    def __init__(self, confirmation: SessionConfirmation) -> None:
        self.confirmation = confirmation
        self.granted: bool | None = None

    async def handle(
        self, text: str, locale: str | None = None
    ) -> ToolResult | Clarification | None:
        self.granted = await self.confirmation.confirm(
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
        return ToolResult.success("system.empty_trash", speech="Emptied")


@pytest.mark.asyncio
async def test_a_turn_asks_before_it_acts(tmp_path: Path) -> None:
    """The question comes back as the turn's answer, and the turn waits.

    HTTP cannot hold a question open, so the turn runs as a task: /api/turn
    returns the question, /api/confirm resumes it.
    """
    confirmation = SessionConfirmation()
    core = Destructive(confirmation)

    async with surface(tmp_path, core, confirmation=confirmation) as (web, base):
        async with httpx.AsyncClient() as client:
            asked = await client.post(
                f"{base}/api/turn",
                json={"text": "empty the trash"},
                headers=headers(web.token),
            )
            # The application and the assurance travel with the question: the
            # page decides what it can answer and what to offer, and cannot
            # decide either without being told.
            assert asked.json() == {
                "outcome": "confirm",
                "tool": "system.empty_trash",
                "risk": "destructive",
                "arguments": {"count": 3},
                "application": None,
                "assurance": "ack",
            }
            assert core.granted is None, "nothing ran while the question stood"

            done = await client.post(
                f"{base}/api/confirm",
                json={"granted": True},
                headers=headers(web.token),
            )

        assert core.granted is True
        assert done.json()["outcome"] == "ran"
        assert done.json()["speech"] == "Emptied"


@pytest.mark.asyncio
async def test_a_declined_question_stops_the_call(tmp_path: Path) -> None:
    confirmation = SessionConfirmation()
    core = Destructive(confirmation)

    async with surface(tmp_path, core, confirmation=confirmation) as (web, base):
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{base}/api/turn",
                json={"text": "empty the trash"},
                headers=headers(web.token),
            )
            done = await client.post(
                f"{base}/api/confirm",
                json={"granted": False},
                headers=headers(web.token),
            )

        assert core.granted is False
        assert done.json()["ok"] is False


@pytest.mark.asyncio
async def test_a_page_that_walks_away_declines(tmp_path: Path) -> None:
    # The browser equivalent of a closed socket: the next turn abandons the
    # unanswered one, and abandoning is a no.
    confirmation = SessionConfirmation()
    core = Destructive(confirmation)

    async with surface(tmp_path, core, confirmation=confirmation) as (web, base):
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{base}/api/turn",
                json={"text": "empty the trash"},
                headers=headers(web.token),
            )
            # No answer. Someone asks for something else instead.
            second = await client.post(
                f"{base}/api/turn",
                json={"text": "empty the trash"},
                headers=headers(web.token),
            )

        assert second.json()["outcome"] == "confirm", "the new turn asks in its turn"


@pytest.mark.asyncio
async def test_answering_when_nothing_asked_is_a_conflict(tmp_path: Path) -> None:
    core = Core()
    async with surface(tmp_path, core) as (web, base):
        async with httpx.AsyncClient() as client:
            answer = await client.post(
                f"{base}/api/confirm",
                json={"granted": True},
                headers=headers(web.token),
            )

        assert answer.status_code == 409


# --- looking --------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_frame_is_answered_and_never_written_down(tmp_path: Path) -> None:
    """The audio route writes a temporary file, because whisper reads a path.
    A vision model takes bytes, so there is nothing to write and nothing to
    delete -- invariant 8, and the shortest life a picture of a room can have.
    """
    seen: list[tuple[bytes, str | None, str | None]] = []

    async def look(image: bytes, text: str | None, locale: str | None) -> ToolResult:
        seen.append((image, text, locale))
        return ToolResult.success("vision.look", speech="Uma secretária.")

    core = Core()
    async with (
        surface(tmp_path, core, look=look) as (web, base),
        httpx.AsyncClient() as client,
    ):
        answer = await client.post(
            f"{base}/api/vision",
            json={
                "image": base64.b64encode(b"a frame").decode(),
                "text": "o que é isto?",
                "locale": "pt-PT",
            },
            headers=headers(web.token),
        )

    assert answer.json()["speech"] == "Uma secretária."
    assert seen == [(b"a frame", "o que é isto?", "pt-PT")]
    # Nothing typed a sentence on the user's behalf.
    assert core.asked == []
    assert list(tmp_path.glob("*.jpg")) == []
    assert list(tmp_path.glob("*.png")) == []


@pytest.mark.asyncio
async def test_no_words_means_describe_it(tmp_path: Path) -> None:
    seen: list[str | None] = []

    async def look(image: bytes, text: str | None, locale: str | None) -> ToolResult:
        seen.append(text)
        return ToolResult.success("vision.look", speech="A lamp.")

    async with (
        surface(tmp_path, Core(), look=look) as (web, base),
        httpx.AsyncClient() as client,
    ):
        await client.post(
            f"{base}/api/vision",
            json={"image": base64.b64encode(b"a frame").decode(), "text": "  "},
            headers=headers(web.token),
        )

    assert seen == [None]


@pytest.mark.asyncio
async def test_a_frame_that_is_not_base64_is_refused(tmp_path: Path) -> None:
    async def look(image: bytes, text: str | None, locale: str | None) -> ToolResult:
        raise AssertionError("nothing should have reached the model")

    async with (
        surface(tmp_path, Core(), look=look) as (web, base),
        httpx.AsyncClient() as client,
    ):
        answer = await client.post(
            f"{base}/api/vision",
            json={"image": "not base64 at all!!"},
            headers=headers(web.token),
        )

    assert answer.status_code == 400


@pytest.mark.asyncio
async def test_a_daemon_that_cannot_see_says_so(tmp_path: Path) -> None:
    async with (
        surface(tmp_path, Core()) as (web, base),
        httpx.AsyncClient() as client,
    ):
        answer = await client.post(
            f"{base}/api/vision",
            json={"image": base64.b64encode(b"a frame").decode()},
            headers=headers(web.token),
        )

    assert answer.status_code == 503


@pytest.mark.asyncio
async def test_a_frame_needs_the_token_like_everything_else(tmp_path: Path) -> None:
    async def look(image: bytes, text: str | None, locale: str | None) -> ToolResult:
        raise AssertionError("no token, no answer")

    async with (
        surface(tmp_path, Core(), look=look) as (_web, base),
        httpx.AsyncClient() as client,
    ):
        answer = await client.post(
            f"{base}/api/vision",
            json={"image": base64.b64encode(b"a frame").decode()},
        )

    assert answer.status_code == 401


@pytest.mark.asyncio
async def test_always_sets_the_level_for_the_application_asked_about(
    tmp_path: Path,
) -> None:
    remembered: list[tuple[str, AccessLevel]] = []
    confirmation = SessionConfirmation()

    class Asking:
        async def handle(
            self, text: str, locale: str | None = None
        ) -> ToolResult | Clarification | None:
            await confirmation.confirm(
                ConfirmationRequest(
                    tool="applications.open",
                    risk=RiskLevel.SENSITIVE,
                    application="Photos",
                )
            )
            return ToolResult.success("applications.open", speech="Opening Photos")

    async with (
        surface(
            tmp_path,
            Asking(),
            confirmation=confirmation,
            remember=lambda name, level: remembered.append((name, level)),
        ) as (web, base),
        httpx.AsyncClient() as client,
    ):
        asked = await client.post(
            f"{base}/api/turn", json={"text": "open Photos"}, headers=headers(web.token)
        )
        assert asked.json()["application"] == "Photos"

        await client.post(
            f"{base}/api/confirm",
            json={"granted": True, "remember": "open"},
            headers=headers(web.token),
        )

    assert remembered == [("Photos", AccessLevel.OPEN)]


@pytest.mark.asyncio
async def test_a_page_cannot_answer_what_only_the_app_can(tmp_path: Path) -> None:
    """`verify` asks macOS to establish who is at the machine.

    A browser page cannot do that -- `getUserMedia` asks in the browser's name
    and there is no equivalent for the owner's password -- so it declines
    rather than answering with a click.
    """
    confirmation = SessionConfirmation()
    reached: list[bool] = []

    class Asking:
        async def handle(
            self, text: str, locale: str | None = None
        ) -> ToolResult | Clarification | None:
            granted = await confirmation.confirm(
                ConfirmationRequest(
                    tool="mail.send",
                    risk=RiskLevel.SENSITIVE,
                    application="Mail",
                    assurance=Assurance.OWNER,
                )
            )
            reached.append(granted)
            return ToolResult.success("mail.send")

    async with (
        surface(tmp_path, Asking(), confirmation=confirmation) as (web, base),
        httpx.AsyncClient() as client,
    ):
        answer = await client.post(
            f"{base}/api/turn", json={"text": "send it"}, headers=headers(web.token)
        )

    # The turn finished without ever asking the page.
    assert answer.json()["outcome"] == "ran"
    assert reached == [False]
