"""The IPC contract, and the source of truth for three languages.

Authored in Pydantic because that is already how every schema in this project
is written, and exported to JSON Schema in `protocol/generated/`, which is what
Rust and TypeScript consume. The export is committed and CI regenerates it: if
these types and that artifact ever disagree, the build says so rather than the
three views drifting quietly apart.

Two asymmetric families, deliberately not one:

* **Commands** travel native -> Python. They are requests, they carry an `id`,
  and exactly one response comes back with the same `id`.
* **Events** travel Python -> native. They are pushed, they have no `id`, and
  nothing answers them.

Collapsing these into one envelope would mean every message carrying fields
that are meaningless in one direction, and a reader that cannot tell whether
silence is an answer.

Speech crosses as intent, never audio: Python asks for a sentence to be spoken,
and the native layer owns the audio device.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from ev.domain.permissions import Permission, PermissionState
from ev.domain.risk import RiskLevel

PROTOCOL_VERSION = "1.0"
"""Major.minor. The handshake compares it exactly: a mismatch refuses the
connection rather than degrading into a conversation neither side understands.
"""


class Message(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- commands: native -> Python -------------------------------------------


class Hello(Message):
    """First message on every connection. Nothing else is served until it is
    accepted."""

    type: Literal["hello"] = "hello"
    protocol: str = Field(description="The protocol version the client speaks.")
    client: str = Field(description="Who is connecting, for the log.")


class UtteranceSubmit(Message):
    type: Literal["utterance.submit"] = "utterance.submit"
    text: str = Field(min_length=1, max_length=4000)
    locale: str | None = Field(
        default=None,
        description="The session locale, e.g. pt-PT. Carried, never used to "
        "translate the utterance before routing.",
    )


class ConfirmationRespond(Message):
    type: Literal["confirmation.respond"] = "confirmation.respond"
    request: str = Field(description="The id of the confirmation.required event.")
    granted: bool


class SessionCancel(Message):
    type: Literal["session.cancel"] = "session.cancel"


Command = Annotated[
    Hello | UtteranceSubmit | ConfirmationRespond | SessionCancel,
    Field(discriminator="type"),
]


class Request(Message):
    """A command with an id. Exactly one `Response` carries the same id back."""

    id: str
    command: Command


class ResponseError(Message):
    code: str
    message: str


class Response(Message):
    id: str
    ok: bool
    payload: dict[str, object] = Field(default_factory=dict)
    error: ResponseError | None = None


# --- events: Python -> native ---------------------------------------------


class TranscriptionPartial(Message):
    type: Literal["transcription.partial"] = "transcription.partial"
    text: str


class SpeechRequested(Message):
    """Intent, not audio. The native layer owns the device."""

    type: Literal["speech.requested"] = "speech.requested"
    text: str
    voice: str = Field(description="A locale, e.g. pt-PT.")
    interrupt: bool = False


class ConfirmationRequired(Message):
    type: Literal["confirmation.required"] = "confirmation.required"
    id: str = Field(description="Echoed back in confirmation.respond.")
    tool: str
    risk: RiskLevel
    arguments: dict[str, object] = Field(default_factory=dict)


class ToolCompleted(Message):
    type: Literal["tool.completed"] = "tool.completed"
    tool: str
    ok: bool
    speech: str | None = None
    error: str | None = None


class StateChanged(Message):
    type: Literal["state.changed"] = "state.changed"
    state: Literal["idle", "listening", "thinking", "acting", "speaking"]


class PermissionChanged(Message):
    """The native host reporting what macOS says. The Python core never infers
    this (invariant 7); it only ever learns it here."""

    type: Literal["permission.changed"] = "permission.changed"
    permission: Permission
    state: PermissionState


Event = Annotated[
    TranscriptionPartial
    | SpeechRequested
    | ConfirmationRequired
    | ToolCompleted
    | StateChanged
    | PermissionChanged,
    Field(discriminator="type"),
]


class Envelope(BaseModel):
    """Everything that crosses the socket, for the generated schema's benefit.

    Each line on the wire is one of these, so a generator emits one type per
    language rather than three unrelated roots.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    request: Request | None = None
    response: Response | None = None
    event: Event | None = None
