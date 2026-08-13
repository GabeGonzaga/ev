"""The IPC contract.

These assert on the shape that crosses the socket, because from phase 1.5 that
shape is read by Rust and TypeScript too, and neither of them runs this suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from ev.domain.permissions import Permission, PermissionState
from ev.domain.risk import RiskLevel
from protocol.export import SCHEMA, render
from protocol.messages import (
    PROTOCOL_VERSION,
    Command,
    ConfirmationRequired,
    ConfirmationRespond,
    Event,
    Hello,
    PermissionChanged,
    Request,
    Response,
    ResponseError,
    SpeechRequested,
    UtteranceSubmit,
)

commands: TypeAdapter[Command] = TypeAdapter(Command)
events: TypeAdapter[Event] = TypeAdapter(Event)


# --- the two families -----------------------------------------------------


def test_a_command_is_chosen_by_its_type() -> None:
    command = commands.validate_python(
        {"type": "utterance.submit", "text": "toca o álbum Blonde"}
    )

    assert isinstance(command, UtteranceSubmit)
    assert command.text == "toca o álbum Blonde"


def test_an_unknown_command_is_refused() -> None:
    # A native host speaking a newer protocol must fail here, not be guessed at.
    with pytest.raises(ValidationError):
        commands.validate_python({"type": "system.wipe_disk"})


def test_a_command_cannot_carry_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        commands.validate_python({"type": "session.cancel", "force": True})


def test_an_event_is_chosen_by_its_type() -> None:
    event = events.validate_python(
        {
            "type": "permission.changed",
            "permission": "microphone",
            "state": "granted",
        }
    )

    assert isinstance(event, PermissionChanged)
    assert event.permission is Permission.MICROPHONE
    assert event.state is PermissionState.GRANTED


def test_events_carry_no_id_and_commands_do() -> None:
    # The asymmetry is the design: a request is answered exactly once, an event
    # is not answered at all. One envelope for both would make silence
    # ambiguous.
    assert "id" not in SpeechRequested.model_fields
    assert "id" in Request.model_fields


def test_speech_crosses_as_intent_not_audio() -> None:
    speech = SpeechRequested(text="A tocar Blonde", voice="pt-PT")

    assert speech.model_dump() == {
        "type": "speech.requested",
        "text": "A tocar Blonde",
        "voice": "pt-PT",
        "interrupt": False,
    }


# --- the wire format ------------------------------------------------------


def test_a_request_round_trips_as_one_json_line() -> None:
    # Newline-delimited JSON: one message per line, so a line break inside a
    # message would desynchronise the stream.
    request = Request(
        id="01", command=UtteranceSubmit(text="abre github.com", locale="pt-PT")
    )

    line = request.model_dump_json()

    assert "\n" not in line
    assert Request.model_validate_json(line) == request


def test_a_response_carries_the_id_it_answers() -> None:
    response = Response(
        id="01", ok=False, error=ResponseError(code="unknown_tool", message="no")
    )

    assert json.loads(response.model_dump_json())["id"] == "01"


def test_a_confirmation_is_correlated_by_id() -> None:
    required = ConfirmationRequired(
        id="c1", tool="system.empty_trash", risk=RiskLevel.DESTRUCTIVE
    )
    answer = ConfirmationRespond(request=required.id, granted=False)

    assert answer.request == required.id


def test_an_utterance_may_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        UtteranceSubmit(text="")


# --- the handshake --------------------------------------------------------


def test_the_version_is_stated_and_exact() -> None:
    # A mismatch refuses the connection rather than degrading into a
    # conversation neither side understands.
    assert PROTOCOL_VERSION == "1.5"
    assert Hello(protocol=PROTOCOL_VERSION, client="tests").protocol == "1.5"


# --- the generated artifact -----------------------------------------------


def test_the_committed_schema_matches_the_types() -> None:
    # The same check `make lint` runs. Here too, because a stale artifact is a
    # silent disagreement between three languages, and only one of them is
    # tested by the rest of this suite.
    assert SCHEMA.exists(), "run: make protocol"
    assert SCHEMA.read_text(encoding="utf-8") == render()


def test_the_schema_names_its_protocol_version() -> None:
    document = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert document["x-ev-protocol-version"] == PROTOCOL_VERSION


def test_every_message_type_appears_in_the_schema() -> None:
    document = SCHEMA.read_text(encoding="utf-8")

    for name in (
        "utterance.submit",
        "audio.submit",
        "history.query",
        "confirmation.respond",
        "session.cancel",
        "transcription.partial",
        "speech.requested",
        "confirmation.required",
        "tool.completed",
        "state.changed",
        "permission.changed",
    ):
        assert name in document, f"{name} missing from the generated schema"


# --- the version, in every language that reads it -------------------------


def test_the_rust_client_speaks_this_version() -> None:
    """The bug this exists for.

    `cargo typify` generates the message types and not the constant beside
    them, so the handshake version was hand-written in the Rust client. Python
    reached 1.4 while it still said 1.2: the app started its own daemon, was
    refused by it, and reported "the core did not answer" -- a version
    mismatch wearing the costume of a daemon that would not start.
    """
    generated = (
        Path(__file__).resolve().parents[2]
        / "protocol"
        / "generated"
        / "rust"
        / "version.rs"
    )

    assert generated.is_file(), "run: make protocol"
    assert f'"{PROTOCOL_VERSION}"' in generated.read_text(encoding="utf-8")
