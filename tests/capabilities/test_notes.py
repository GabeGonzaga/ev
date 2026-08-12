from __future__ import annotations

import pytest
from pydantic import ValidationError

from ev.application.speech import Speaker
from ev.capabilities.notes.adapters import CREATE as CREATE_SCRIPT
from ev.capabilities.notes.adapters import LIST_FOLDERS, NotesAdapter
from ev.capabilities.notes.args import CreateArgs
from ev.capabilities.notes.render import html
from ev.capabilities.notes.service import CREATE, NotesService
from ev.capabilities.notes.tools import notes_tools
from ev.domain.content import CONTENT_MARKER
from ev.domain.permissions import Permission
from ev.domain.results import ToolErrorCode
from ev.infrastructure.macos.applescript import AppleScriptClient, AppleScriptError
from ev.infrastructure.macos.processes import ProcessRunner
from tests.conftest import FakeBin


def marked(schema: object) -> bool:
    """Whether `x-ev-content` appears anywhere in a field's schema."""
    if isinstance(schema, dict):
        return schema.get(CONTENT_MARKER) is True or any(
            marked(value) for value in schema.values()
        )
    if isinstance(schema, list):
        return any(marked(value) for value in schema)
    return False


class Notes:
    """A Notes with two folders that remembers what it was asked to write."""

    def __init__(self, folders: list[str] | None = None) -> None:
        self.names = folders if folders is not None else ["Notes", "Trabalho / 2026"]
        self.written: list[tuple[str, str | None, str | None]] = []

    async def folders(self) -> list[str]:
        return self.names

    async def create(self, title: str, body: str | None, folder: str | None) -> str:
        self.written.append((title, body, folder))
        return title


# --- the body Notes actually stores ---------------------------------------


def test_the_title_leads_the_body() -> None:
    # Notes shows a note's first line as its title. A body that does not start
    # with it leaves the list and the note disagreeing.
    assert html("Compras", "pão").startswith("<h1>Compras</h1>")


def test_the_text_is_escaped_not_interpreted() -> None:
    # A note about <b> is about <b>. Notes stores HTML, so unescaped text is
    # markup, and the note quietly loses what was dictated into it.
    assert "&lt;b&gt;leite&lt;/b&gt;" in html("Compras", "<b>leite</b>")


def test_a_blank_line_survives() -> None:
    assert html("T", "one\n\ntwo") == (
        "<h1>T</h1><div>one</div><div><br></div><div>two</div>"
    )


def test_a_note_with_no_body_is_a_title() -> None:
    assert html("Compras", None) == "<h1>Compras</h1>"


# --- what reaches osascript -----------------------------------------------


@pytest.mark.asyncio
async def test_the_script_and_the_arguments_are_exact(fake_bin: FakeBin) -> None:
    adapter = NotesAdapter(AppleScriptClient(ProcessRunner()))

    await adapter.create("Compras", "pão", "Trabalho / 2026")

    assert fake_bin.argv() == [
        "-e",
        CREATE_SCRIPT,
        "--",
        "Compras",
        "<h1>Compras</h1><div>pão</div>",
        "Trabalho / 2026",
    ]


@pytest.mark.asyncio
async def test_no_folder_is_an_empty_argument_not_a_missing_one(
    fake_bin: FakeBin,
) -> None:
    # The script reads item 3 of argv unconditionally. Leaving it out would
    # fail inside AppleScript rather than here.
    adapter = NotesAdapter(AppleScriptClient(ProcessRunner()))

    await adapter.create("Compras", None, None)

    assert fake_bin.argv()[-1] == ""


def test_the_delimiter_belongs_to_applescript_not_to_notes() -> None:
    # The exact defect that shipped for Music: setting this inside the tell
    # block compiles and then fails at runtime with "Notes got an error".
    body = LIST_FOLDERS[LIST_FOLDERS.index("tell") : LIST_FOLDERS.index("end tell")]

    assert "text item delimiters" not in body
    assert "set AppleScript's text item delimiters" in LIST_FOLDERS


# --- resolving the folder --------------------------------------------------


@pytest.mark.asyncio
async def test_a_spoken_folder_is_matched_against_the_real_ones() -> None:
    # Nobody dictates "Trabalho / 2026" with the slash in it.
    notes = Notes()
    service = NotesService(notes, Speaker("en"))  # type: ignore[arg-type]

    result = await service.create(CreateArgs(title="Ata", folder="trabalho 2026"))

    assert result.ok
    assert notes.written == [("Ata", None, "Trabalho / 2026")]


@pytest.mark.asyncio
async def test_an_unknown_folder_refuses_and_names_the_real_ones() -> None:
    # It refuses rather than creating one: a folder made from a mishearing is
    # a mess that outlives the turn.
    notes = Notes(["Notes", "Recipes"])
    service = NotesService(notes, Speaker("en"))  # type: ignore[arg-type]

    result = await service.create(CreateArgs(title="Ata", folder="Work"))

    assert not result.ok
    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert "Notes, Recipes" in result.error.message
    assert notes.written == []


@pytest.mark.asyncio
async def test_no_folder_asked_for_means_notes_is_never_listed() -> None:
    # The common case must not cost an extra Apple Event.
    class Refusing(Notes):
        async def folders(self) -> list[str]:
            raise AssertionError("nothing asked for a folder")

    notes = Refusing()
    service = NotesService(notes, Speaker("en"))  # type: ignore[arg-type]

    assert (await service.create(CreateArgs(title="Ata"))).ok


@pytest.mark.asyncio
async def test_a_folder_that_disappears_is_an_argument_error() -> None:
    class Vanishing(Notes):
        async def create(self, title: str, body: str | None, folder: str | None) -> str:
            raise AppleScriptError("there is no folder called Notes")

    service = NotesService(Vanishing(), Speaker("en"))  # type: ignore[arg-type]

    result = await service.create(CreateArgs(title="Ata", folder="Notes"))

    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS


# --- what it says ----------------------------------------------------------


@pytest.mark.asyncio
async def test_it_answers_in_the_language_it_was_asked_in() -> None:
    service = NotesService(Notes(), Speaker("pt-PT"))  # type: ignore[arg-type]

    result = await service.create(CreateArgs(title="Compras"))

    assert result.speech == "Guardei Compras nas Notas"


@pytest.mark.asyncio
async def test_a_note_in_a_folder_says_which() -> None:
    service = NotesService(Notes(), Speaker("en"))  # type: ignore[arg-type]

    result = await service.create(CreateArgs(title="Ata", folder="trabalho 2026"))

    assert result.speech == "Saved Ata to Trabalho / 2026"


# --- the schema ------------------------------------------------------------


def test_the_body_is_the_only_field_a_model_may_write() -> None:
    """The generation-path rule, made checkable.

    `CLAUDE.md`: "translate this and save it to Notes" means the body is
    generated and the note title is not. The marker is what says so.
    """
    schema = CreateArgs.model_json_schema()

    # `body` is optional, so pydantic writes it as an anyOf and the marker
    # sits on the string branch. It has to be looked for, not read off the
    # top -- a check that only worked on required fields would pass by
    # accident on a field that never had the marker at all.
    assert marked(schema["properties"]["body"])
    assert not marked(schema["properties"]["title"])
    assert not marked(schema["properties"]["folder"])


def test_a_note_needs_a_title() -> None:
    with pytest.raises(ValidationError):
        CreateArgs(body="pão")  # type: ignore[call-arg]


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError):
        CreateArgs(title="Compras", account="iCloud")  # type: ignore[call-arg]


def test_writing_a_note_declares_apple_events() -> None:
    (spec,) = notes_tools(NotesService(Notes()))  # type: ignore[arg-type]

    assert spec.name == CREATE
    assert spec.permissions == frozenset({Permission.APPLE_EVENTS})
