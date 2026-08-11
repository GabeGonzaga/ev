from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from ev.application.policy import PermissionLedger, PermissionPolicy
from ev.capabilities.language.args import TranslateArgs
from ev.capabilities.language.service import LanguageService
from ev.capabilities.language.tools import language_tools
from ev.domain.content import CONTENT_MARKER
from ev.domain.results import ToolErrorCode
from ev.domain.risk import RiskLevel
from ev.registry import CallRecord, Registry


class FakeModel:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[dict[str, str]] = []

    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any] | None = None
    ) -> str:
        self.messages = messages
        return self.content


class Failing:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any] | None = None
    ) -> str:
        raise self.error


def translating(text: str) -> FakeModel:
    return FakeModel(json.dumps({"text": text}))


class CollectingJournal:
    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    async def record(self, record: CallRecord) -> None:
        self.records.append(record)


class RefusingConfirmation:
    async def confirm(self, request: object) -> bool:  # pragma: no cover
        raise AssertionError("translation must not require confirmation")


def build(model: Any) -> Registry:
    registry = Registry(
        policy=PermissionPolicy(PermissionLedger()),
        confirmation=RefusingConfirmation(),
        journal=CollectingJournal(),
    )
    for spec in language_tools(LanguageService(model)):
        registry.register(spec)
    return registry


# --- arguments ------------------------------------------------------------


def test_the_text_is_content_typed_and_says_so_in_the_schema() -> None:
    # The one field in the project that may hold model-written prose. The
    # marker is what makes that checkable rather than assumed.
    schema = TranslateArgs.model_json_schema()

    assert schema["properties"]["text"][CONTENT_MARKER] is True
    assert CONTENT_MARKER not in schema["properties"]["to"]


def test_the_target_language_is_a_closed_set() -> None:
    # "to" selects what happens, so it is not free text and never generated.
    with pytest.raises(ValidationError):
        TranslateArgs.model_validate({"text": "bom dia", "to": "klingon"})


def test_empty_text_is_refused() -> None:
    with pytest.raises(ValidationError):
        TranslateArgs.model_validate({"text": "", "to": "en"})


# --- the generation path --------------------------------------------------


@pytest.mark.asyncio
async def test_the_text_reaches_the_model_verbatim() -> None:
    model = translating("Good morning")
    service = LanguageService(model)

    await service.translate(TranslateArgs(text="Bom dia", to="en"))

    assert model.messages[-1] == {"role": "user", "content": "Bom dia"}


@pytest.mark.asyncio
async def test_european_portuguese_is_asked_for_by_name() -> None:
    # Multilingual models default to Brazilian. Saying "Portuguese" is not
    # enough, and the golden cases are where the drift would show.
    model = translating("Bom dia")
    service = LanguageService(model)

    await service.translate(TranslateArgs(text="Good morning", to="pt-PT"))

    system = model.messages[0]["content"]
    assert "European Portuguese" in system
    assert "never Brazilian" in system


@pytest.mark.asyncio
async def test_identifiers_are_protected_by_the_prompt() -> None:
    model = translating("qualquer coisa")
    service = LanguageService(model)

    await service.translate(TranslateArgs(text="open Safari", to="pt-PT"))

    system = model.messages[0]["content"]
    assert "URLs" in system
    assert "application names" in system


@pytest.mark.asyncio
async def test_a_translation_comes_back_as_the_result() -> None:
    registry = build(translating("Bom dia"))

    result = await registry.call(
        "language.translate", {"text": "Good morning", "to": "pt-PT"}
    )

    assert result.ok
    assert result.data["text"] == "Bom dia"
    assert result.speech == "Bom dia"


# --- failure returns the original -----------------------------------------


@pytest.mark.asyncio
async def test_a_failure_returns_the_original_text() -> None:
    # The contract from CLAUDE.md: never guessed content. Losing the user's
    # words in order to report an error is worse than the error.
    registry = build(Failing(RuntimeError("model exploded")))

    result = await registry.call("language.translate", {"text": "Bom dia", "to": "en"})

    assert not result.ok
    assert result.error is not None
    assert result.error.code is ToolErrorCode.ADAPTER_FAILED
    assert result.data == {"text": "Bom dia", "translated": False}


@pytest.mark.asyncio
async def test_unparseable_output_is_a_failure_not_a_guess() -> None:
    registry = build(FakeModel("Bom dia, I think?"))

    result = await registry.call(
        "language.translate", {"text": "Good morning", "to": "pt-PT"}
    )

    assert not result.ok
    assert result.data["text"] == "Good morning"


@pytest.mark.asyncio
async def test_an_empty_translation_is_a_failure() -> None:
    registry = build(translating("   "))

    result = await registry.call("language.translate", {"text": "Bom dia", "to": "en"})

    assert not result.ok
    assert result.data["text"] == "Bom dia"


# --- declaration ----------------------------------------------------------


def test_translation_is_safe_and_needs_no_permission() -> None:
    (spec,) = language_tools(LanguageService(translating("x")))

    assert spec.risk is RiskLevel.SAFE
    assert spec.permissions == frozenset()
