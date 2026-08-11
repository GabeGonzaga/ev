"""Tier 2, with no model.

The completion port is faked, so these assert what the router sends, what it
accepts back and what it refuses. Whether a real model answers well is a
different question, measured by `make eval` against the golden cases.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ev.router.model import ModelRouter, resolution_schema, system_prompt

SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "browser.open_url",
            "description": "Open an http or https URL in the default browser.",
            "parameters": {"type": "object", "properties": {"url": {"type": "string"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "music.play",
            "description": "Play an album, track or playlist.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        },
    },
]


class FakeCompletion:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[dict[str, str]] = []
        self.schema: dict[str, Any] = {}

    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any]
    ) -> str:
        self.messages = messages
        self.schema = schema
        return self.content


class Exploding:
    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any]
    ) -> str:  # pragma: no cover
        raise AssertionError("the model must not be called")


def answer(**fields: Any) -> str:
    payload = {"tool": "music.play", "arguments": {}, "confidence": 0.9}
    payload.update(fields)
    return json.dumps(payload)


# --- what is sent ---------------------------------------------------------


def test_the_schema_admits_only_registered_tools_or_null() -> None:
    schema = resolution_schema(["browser.open_url", "music.play"])

    assert schema["properties"]["tool"]["enum"] == [
        "browser.open_url",
        "music.play",
        None,
    ]


def test_confidence_is_bounded_in_the_schema_not_clamped_after() -> None:
    confidence = resolution_schema(["a.b"])["properties"]["confidence"]

    assert confidence["minimum"] == 0
    assert confidence["maximum"] == 1


def test_the_prompt_lists_every_tool() -> None:
    prompt = system_prompt(SPECS)

    assert "browser.open_url" in prompt
    assert "music.play" in prompt


def test_the_prompt_forbids_translating_the_arguments() -> None:
    # The proper nouns in an utterance are the arguments. A translated album
    # name is a failure that looks like a success.
    prompt = system_prompt(SPECS)

    assert "Never translate" in prompt


@pytest.mark.asyncio
async def test_the_utterance_is_sent_verbatim() -> None:
    completion = FakeCompletion(answer())

    await ModelRouter(completion, SPECS).resolve("  Toca o álbum Blonde  ")

    # Not normalised, not lowercased, not translated on the way in.
    assert completion.messages[-1] == {
        "role": "user",
        "content": "  Toca o álbum Blonde  ",
    }


@pytest.mark.asyncio
async def test_an_empty_registry_never_reaches_the_model() -> None:
    assert await ModelRouter(Exploding(), []).resolve("play something") is None


# --- what comes back ------------------------------------------------------


@pytest.mark.asyncio
async def test_a_good_answer_becomes_a_resolution() -> None:
    completion = FakeCompletion(
        answer(
            tool="music.play",
            arguments={"name": "Blonde", "kind": "album"},
            confidence=0.82,
            response="A tocar Blonde.",
        )
    )

    resolution = await ModelRouter(completion, SPECS).resolve("toca o álbum Blonde")

    assert resolution is not None
    assert resolution.tool == "music.play"
    assert resolution.arguments == {"name": "Blonde", "kind": "album"}
    assert resolution.confidence == 0.82
    assert resolution.response == "A tocar Blonde."


@pytest.mark.asyncio
async def test_a_null_tool_is_how_the_model_declines() -> None:
    # Without a way to say "none of these", being forced to name a tool turns
    # "I do not know" into a confident wrong answer.
    completion = FakeCompletion(json.dumps({"tool": None, "confidence": 0.1}))

    assert await ModelRouter(completion, SPECS).resolve("what is the weather") is None


@pytest.mark.asyncio
async def test_malformed_json_is_refused_not_repaired() -> None:
    completion = FakeCompletion('{"tool": "music.play", "argum')

    assert await ModelRouter(completion, SPECS).resolve("toca Blonde") is None


@pytest.mark.asyncio
async def test_a_tool_that_does_not_exist_is_refused() -> None:
    # The enum should have prevented it; refusing here keeps an invented name
    # out of the journal and out of the confidence numbers.
    completion = FakeCompletion(answer(tool="system.wipe_disk"))

    assert await ModelRouter(completion, SPECS).resolve("wipe the disk") is None


@pytest.mark.asyncio
async def test_confidence_outside_the_range_is_refused() -> None:
    completion = FakeCompletion(answer(confidence=1.7))

    assert await ModelRouter(completion, SPECS).resolve("toca Blonde") is None


@pytest.mark.asyncio
async def test_a_missing_confidence_is_refused() -> None:
    completion = FakeCompletion(json.dumps({"tool": "music.play", "arguments": {}}))

    assert await ModelRouter(completion, SPECS).resolve("toca Blonde") is None


@pytest.mark.asyncio
async def test_a_non_object_answer_is_refused() -> None:
    completion = FakeCompletion(json.dumps(["music.play"]))

    assert await ModelRouter(completion, SPECS).resolve("toca Blonde") is None


@pytest.mark.asyncio
async def test_arguments_are_passed_through_unvalidated() -> None:
    # The router does not know the tool's args model, and must not pretend to.
    # Registry.call() is what validates, at the one door.
    completion = FakeCompletion(answer(arguments={"nonsense": [1, 2, 3]}))

    resolution = await ModelRouter(completion, SPECS).resolve("toca Blonde")

    assert resolution is not None
    assert resolution.arguments == {"nonsense": [1, 2, 3]}
