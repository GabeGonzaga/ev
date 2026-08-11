"""What every tool returns.

`Registry.call()` is the single door (CLAUDE.md, invariant 4), so this is the
one shape the CLI, the journal and later the IPC layer all read. Failures are
typed: callers branch on a code, never on the wording of a message.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolErrorCode(StrEnum):
    """Why a call did not run, or did not finish."""

    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    """Arguments failed validation against the tool's args model."""

    PERMISSION_DENIED = "permission_denied"
    CONFIRMATION_DECLINED = "confirmation_declined"
    ADAPTER_FAILED = "adapter_failed"
    """The system call ran and failed. The only code that implies a side effect."""

    TIMEOUT = "timeout"


class ToolError(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: ToolErrorCode
    message: str
    """For the log and the user. Never parsed."""


class Clarification(BaseModel):
    """Understood, but not confidently enough to act.

    Carries what E.V. thinks it heard so the user can confirm or correct it.
    No wording lives here: the phrasing belongs to whatever is talking to the
    user, and it has to be in the language they used.
    """

    model_config = ConfigDict(frozen=True)

    tool: str
    arguments: dict[str, object] = Field(default_factory=dict)
    confidence: float
    response: str | None = None
    """The model's own line, in the language of the request, when it gave one."""


class ToolResult(BaseModel):
    """The outcome of one `Registry.call()`."""

    model_config = ConfigDict(frozen=True)

    ok: bool
    tool: str
    data: dict[str, object] = Field(default_factory=dict)
    error: ToolError | None = None
    speech: str | None = None
    """The line to say or print. Concise by default: it is on the voice path."""

    @model_validator(mode="after")
    def _error_matches_ok(self) -> Self:
        if self.ok and self.error is not None:
            raise ValueError("a successful ToolResult cannot carry an error")
        if not self.ok and self.error is None:
            raise ValueError("a failed ToolResult must carry an error")
        return self

    @classmethod
    def success(
        cls,
        tool: str,
        *,
        data: dict[str, object] | None = None,
        speech: str | None = None,
    ) -> Self:
        return cls(ok=True, tool=tool, data=data or {}, speech=speech)

    @classmethod
    def failure(
        cls,
        tool: str,
        code: ToolErrorCode,
        message: str,
        *,
        speech: str | None = None,
    ) -> Self:
        return cls(
            ok=False,
            tool=tool,
            error=ToolError(code=code, message=message),
            speech=speech,
        )
