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

from ev.domain.journal import JournalEntry
from ev.domain.permissions import Permission, PermissionState
from ev.domain.risk import RiskLevel

MAX_AUDIO_BASE64 = 8_000_000
"""About three minutes of 16 kHz mono, encoded. A bound rather than a target:
push-to-talk utterances are seconds long, and an unbounded field on a socket is
a promise to buffer whatever arrives."""

PROTOCOL_VERSION = "1.3"
"""Major.minor. The handshake compares it exactly: a mismatch refuses the
connection rather than degrading into a conversation neither side understands.

1.1 added `audio.submit`; 1.2 added `history.query`; 1.3 gave it `query`. A
client that knows an
earlier version is refused rather than served a subset, because "some of the
protocol" is not a protocol.
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


class AudioSubmit(Message):
    """Recorded speech, on its way to be transcribed.

    The host captures, because the microphone is a TCC surface and TCC grants
    attach to a code signature. The core transcribes, because that is where
    `SpeechRecognizer` lives and where the engine stays replaceable (ADR 0018).

    Base64 rather than a file path: a path means the audio is written to disk
    by one process and read by another, and neither owns deleting it. ~2.5
    seconds of 16 kHz mono is about 100 KB encoded, which is nothing on a local
    socket.
    """

    type: Literal["audio.submit"] = "audio.submit"
    audio: str = Field(
        max_length=MAX_AUDIO_BASE64,
        description="base64 of a mono 16-bit PCM WAV.",
    )
    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    locale: str | None = Field(
        default=None,
        description="The language to transcribe as. Never 'auto': auto-detect "
        "is unreliable on short utterances, and a misdetected language becomes "
        "a tool argument.",
    )


class ConfirmationRespond(Message):
    type: Literal["confirmation.respond"] = "confirmation.respond"
    request: str = Field(description="The id of the confirmation.required event.")
    granted: bool


class HistoryQuery(Message):
    """What E.V. has done, newest first.

    A request rather than an event: history is asked for, not pushed. The
    answer arrives in the response payload as `entries`, shaped like
    `JournalEntry` below.
    """

    type: Literal["history.query"] = "history.query"
    limit: int = Field(default=20, ge=1, le=500)
    before: int | None = Field(
        default=None, description="Only entries older than this id. For paging."
    )
    query: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Search the trail instead of paging it: a tool, an album, a "
            "note's title. Accents are folded. Ignores `before`, because a "
            "search is not a page."
        ),
    )


class SessionCancel(Message):
    type: Literal["session.cancel"] = "session.cancel"


Command = Annotated[
    Hello
    | UtteranceSubmit
    | AudioSubmit
    | ConfirmationRespond
    | HistoryQuery
    | SessionCancel,
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


class HistoryPage(BaseModel):
    """What a `history.query` answers with, inside the response payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: list[JournalEntry] = Field(default_factory=list)


class Envelope(BaseModel):
    """Everything that crosses the socket, for the generated schema's benefit.

    Each line on the wire is one of these, so a generator emits one type per
    language rather than three unrelated roots.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    request: Request | None = None
    response: Response | None = None
    event: Event | None = None

    # Not a line on the wire: a response payload is an untyped object, and
    # this is how the shape inside one reaches the generated Rust and
    # TypeScript. A catalogue entry, and the comment is here so nobody
    # mistakes it for a message.
    page: HistoryPage | None = None
