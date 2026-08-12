"""A named list of tool calls E.V. can run, edit, version, import and export.

`CLAUDE.md` is blunt about why this exists: Shortcuts cannot be created
programmatically, `.shortcut` files are encrypted with no public format, and
there is no public creation API. So E.V. has its own format, and the point of
owning it is that everything about it is inspectable -- a file you can read,
diff and delete.

A macro is *validated when it is saved*, not when it is run. A file full of
calls that will fail at step four is a trap, and the moment to find that is
while writing it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MacroStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: str
    arguments: dict[str, object] = Field(default_factory=dict)


class Macro(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    version: int = Field(default=1, ge=1)
    """Bumped by whoever edits it. E.V. does not guess whether a change
    mattered; the number is there so an export can be compared to an import."""

    steps: list[MacroStep] = Field(min_length=1, max_length=50)
