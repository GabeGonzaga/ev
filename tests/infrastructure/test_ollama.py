"""The Ollama client, with no Ollama and no network.

Every request is served by an httpx MockTransport, so this runs on the CI
Linux box exactly as it runs here. The tests that need real weights are
`make eval`, and they are not in the suite.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from ev.infrastructure.ollama.client import (
    ModelMissing,
    OllamaClient,
    OllamaError,
    OllamaUnavailable,
)
from ev.infrastructure.ollama.settings import ModelSettings, OllamaSettings

pytestmark = pytest.mark.asyncio

MODEL = ModelSettings(name="qwen3:8b")


def transport(
    handler: Any,
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def client(handler: Any) -> OllamaClient:
    return OllamaClient(OllamaSettings(), transport=transport(handler))


def answering(content: str) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": content}})

    return handler


# --- the request ----------------------------------------------------------


async def test_the_request_carries_model_keep_alive_and_thinking() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "ok"}})

    await client(handler).chat(MODEL, [{"role": "user", "content": "hi"}])

    assert seen["model"] == "qwen3:8b"
    assert seen["stream"] is False
    assert seen["keep_alive"] == "30m"
    # A router that stops to reason does not fit the budget.
    assert seen["think"] is False


async def test_a_schema_is_sent_as_format() -> None:
    seen: dict[str, Any] = {}
    schema = {"type": "object", "properties": {"tool": {"type": "string"}}}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "{}"}})

    await client(handler).chat(MODEL, [], schema=schema)

    # Constrained while generating, rather than repaired afterwards.
    assert seen["format"] == schema


async def test_no_schema_means_no_format_key() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "prose"}})

    await client(handler).chat(MODEL, [])

    assert "format" not in seen


async def test_the_content_comes_back_unparsed() -> None:
    assert await client(answering('{"tool": "music.play"}')).chat(MODEL, []) == (
        '{"tool": "music.play"}'
    )


# --- failures -------------------------------------------------------------


async def test_a_dead_ollama_says_so_with_the_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    with pytest.raises(OllamaUnavailable, match="Is it running"):
        await client(handler).chat(MODEL, [])


async def test_a_missing_model_lists_what_is_installed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "qwen3:14b"}, {"name": "gemma3:12b"}]}
            )
        return httpx.Response(404, json={"error": "model not found"})

    with pytest.raises(ModelMissing) as caught:
        await client(handler).chat(MODEL, [])

    message = str(caught.value)
    assert "qwen3:14b" in message
    assert "ollama pull qwen3:8b" in message


async def test_a_timeout_is_a_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(TimeoutError):
        await client(handler).chat(MODEL, [])


async def test_another_error_carries_the_status_and_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="out of memory")

    with pytest.raises(OllamaError, match="500: out of memory"):
        await client(handler).chat(MODEL, [])


async def test_installed_returns_the_names_sorted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"models": [{"name": "qwen3:8b"}, {"name": "gemma3:12b"}]}
        )

    assert await client(handler).installed() == ["gemma3:12b", "qwen3:8b"]
