from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ev.application.speech import Speaker
from ev.capabilities.reminders.adapters import CREATE as CREATE_SCRIPT
from ev.capabilities.reminders.adapters import (
    LIST_LISTS,
    RemindersAdapter,
    seconds_into_the_day,
)
from ev.capabilities.reminders.args import CreateArgs
from ev.capabilities.reminders.service import CREATE, RemindersService
from ev.capabilities.reminders.tools import reminders_tools
from ev.domain.content import CONTENT_MARKER
from ev.domain.permissions import Permission
from ev.domain.results import ToolErrorCode
from ev.infrastructure.macos.applescript import AppleScriptClient, AppleScriptError
from ev.infrastructure.macos.processes import ProcessRunner
from tests.conftest import FakeBin

NOW = datetime(2026, 8, 12, 18, 0)


def clock() -> datetime:
    return NOW


class Reminders:
    """A Reminders with two lists that remembers what it was asked to add."""

    def __init__(self, lists: list[str] | None = None) -> None:
        self.names = lists if lists is not None else ["Reminders", "Compras 🛒"]
        self.added: list[tuple[str, datetime | None, str | None]] = []

    async def lists(self) -> list[str]:
        return self.names

    async def create(
        self, title: str, due: datetime | None, list_name: str | None
    ) -> str:
        self.added.append((title, due, list_name))
        return title


def service(
    reminders: Reminders | None = None, locale: str = "en"
) -> tuple[RemindersService, Reminders]:
    adapter = reminders or Reminders()
    return (
        RemindersService(adapter, Speaker(locale), clock=clock),  # type: ignore[arg-type]
        adapter,
    )


# --- the date -------------------------------------------------------------


def test_the_time_is_seconds_since_midnight() -> None:
    # AppleScript's `time` property, which is what the script sets.
    assert seconds_into_the_day(datetime(2026, 8, 13, 9, 30)) == 9 * 3600 + 30 * 60


@pytest.mark.asyncio
async def test_the_date_travels_as_numbers_not_as_text(fake_bin: FakeBin) -> None:
    """`date "13/08/2026"` means different days on differently configured
    Macs. Nothing here is parsed by AppleScript."""
    adapter = RemindersAdapter(AppleScriptClient(ProcessRunner()))

    await adapter.create("Dentista", datetime(2026, 8, 13, 9, 30), None)

    assert fake_bin.argv() == [
        "-e",
        CREATE_SCRIPT,
        "--",
        "Dentista",
        "",
        "2026",
        "8",
        "13",
        str(9 * 3600 + 30 * 60),
    ]


@pytest.mark.asyncio
async def test_no_date_is_four_empty_arguments(fake_bin: FakeBin) -> None:
    # The script reads seven arguments unconditionally: a short argv would
    # fail inside AppleScript rather than here.
    adapter = RemindersAdapter(AppleScriptClient(ProcessRunner()))

    await adapter.create("Dentista", None, None)

    assert fake_bin.argv()[-4:] == ["", "", "", ""]


def test_the_day_is_anchored_before_the_month_is_set() -> None:
    """On the 31st, setting the month to February gives the 3rd of March.

    The order in the script is the fix, and it is the kind of thing that gets
    tidied into a bug by someone reading it later.
    """
    body = CREATE_SCRIPT[CREATE_SCRIPT.index("set theDate to current date") :]

    anchor = body.index("set day of theDate to 1")
    month = body.index("set month of theDate")

    assert anchor < month


def test_the_current_date_is_asked_for_outside_the_tell_block() -> None:
    # `current date` is Standard Additions, not something Reminders answers.
    # This file has been bitten once by sending a global to an application.
    assert CREATE_SCRIPT.index("current date") < CREATE_SCRIPT.index(
        'tell application "Reminders"'
    )


def test_the_delimiter_belongs_to_applescript_not_to_reminders() -> None:
    body = LIST_LISTS[LIST_LISTS.index("tell") : LIST_LISTS.index("end tell")]

    assert "text item delimiters" not in body


# --- a date that cannot be right ------------------------------------------


@pytest.mark.asyncio
async def test_a_reminder_in_the_past_is_refused() -> None:
    """The way a model gets a date wrong is to be confidently in the wrong
    year. Reminders accepts it, fires immediately, and calls it a success."""
    made, reminders = service()

    result = await made.create(
        CreateArgs(title="Dentista", due=datetime(2024, 8, 13, 9, 0))
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS
    assert "13/08 09:00" in result.error.message
    assert reminders.added == []


@pytest.mark.asyncio
async def test_a_few_minutes_ago_is_not_the_past() -> None:
    # "Remind me at six" said at 18:02 is a real request, and so is a turn
    # that took a second to route.
    made, reminders = service()

    result = await made.create(CreateArgs(title="Now", due=NOW - timedelta(minutes=20)))

    assert result.ok
    assert len(reminders.added) == 1


@pytest.mark.asyncio
async def test_an_offset_is_converted_rather_than_refused() -> None:
    # A model asked for ISO 8601 sometimes writes a `Z`. That is answerable.
    made, reminders = service()

    await made.create(
        CreateArgs(title="Dentista", due=datetime(2026, 8, 13, 9, 0, tzinfo=UTC))
    )

    (_, due, _) = reminders.added[0]
    assert due is not None and due.tzinfo is None


# --- the list -------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_spoken_list_is_matched_against_the_real_ones() -> None:
    made, reminders = service()

    result = await made.create(CreateArgs(title="Leite", list="compras"))

    assert result.ok
    assert reminders.added[0][2] == "Compras 🛒"


@pytest.mark.asyncio
async def test_an_unknown_list_refuses_and_names_the_real_ones() -> None:
    made, reminders = service(Reminders(["Reminders", "Work"]))

    result = await made.create(CreateArgs(title="Leite", list="Compras"))

    assert not result.ok
    assert result.error is not None
    assert "Reminders, Work" in result.error.message
    assert reminders.added == []


@pytest.mark.asyncio
async def test_no_list_asked_for_means_reminders_is_never_listed() -> None:
    class Refusing(Reminders):
        async def lists(self) -> list[str]:
            raise AssertionError("nothing asked for a list")

    made, _ = service(Refusing())

    assert (await made.create(CreateArgs(title="Leite"))).ok


@pytest.mark.asyncio
async def test_a_list_that_disappears_is_an_argument_error() -> None:
    class Vanishing(Reminders):
        async def create(
            self, title: str, due: datetime | None, list_name: str | None
        ) -> str:
            raise AppleScriptError("there is no list called Work")

    made, _ = service(Vanishing(["Work"]))

    result = await made.create(CreateArgs(title="Leite", list="Work"))

    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_ARGUMENTS


# --- what it says ---------------------------------------------------------


@pytest.mark.asyncio
async def test_it_answers_in_the_language_it_was_asked_in() -> None:
    made, _ = service(locale="pt-PT")

    result = await made.create(
        CreateArgs(title="Comprar pão", due=datetime(2026, 8, 13, 9, 0))
    )

    assert result.speech == "Lembrete criado: Comprar pão, 13/08 09:00"


@pytest.mark.asyncio
async def test_a_reminder_with_no_date_does_not_invent_one() -> None:
    made, _ = service()

    result = await made.create(CreateArgs(title="Call the dentist"))

    assert result.speech == "Reminder set: Call the dentist"


# --- the schema -----------------------------------------------------------


def test_nothing_here_may_be_written_by_a_model() -> None:
    """A reminder is a line and a time.

    There was a `notes` field. Measured against qwen3:8b it came back holding
    the request itself -- "remind me to call the dentist tomorrow at nine" as
    the body of a reminder titled "call the dentist" -- and once holding a word
    that was in neither. A field a model reliably misuses does not belong in
    the schema; `notes.create` is where written text goes.
    """
    schema = json.dumps(CreateArgs.model_json_schema())

    assert CONTENT_MARKER not in schema
    assert set(CreateArgs.model_json_schema()["properties"]) == {
        "title",
        "due",
        "list",
    }


def test_a_due_date_is_parsed_not_taken_as_text() -> None:
    assert CreateArgs(title="x", due="2026-08-13T09:00").due == datetime(  # type: ignore[arg-type]
        2026, 8, 13, 9, 0
    )


def test_something_that_is_not_a_date_is_refused() -> None:
    with pytest.raises(ValidationError):
        CreateArgs(title="x", due="amanhã às nove")  # type: ignore[arg-type]


def test_adding_a_reminder_declares_apple_events() -> None:
    (spec,) = reminders_tools(RemindersService(Reminders()))  # type: ignore[arg-type]

    assert spec.name == CREATE
    assert spec.permissions == frozenset({Permission.APPLE_EVENTS})
