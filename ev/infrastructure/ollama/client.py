"""The single Ollama client. Both paths consume it.

Local HTTP to 127.0.0.1 only. This is not the IPC transport -- that one is a
Unix socket precisely because a port is reachable by every process on the
machine, including a browser tab. Here the port belongs to Ollama and is not
ours to choose; nothing E.V. owns listens on it.

Structured output is a JSON Schema handed to Ollama as `format`, so the model
is constrained while generating rather than corrected afterwards. What comes
back is still validated: a constrained decoder makes bad JSON unlikely, not
impossible, and the schema is the router's, not the tool's.
"""

from __future__ import annotations

from base64 import b64encode
from typing import Any

import httpx

from ev.infrastructure.ollama.settings import ModelSettings, OllamaSettings, Role


class OllamaError(Exception):
    """Anything that stopped a call from producing an answer."""


class OllamaUnavailable(OllamaError):
    def __init__(self, host: str) -> None:
        super().__init__(f"no Ollama at {host}. Is it running?")
        self.host = host


class ModelMissing(OllamaError):
    def __init__(self, name: str, installed: list[str]) -> None:
        known = ", ".join(installed) if installed else "nothing"
        super().__init__(
            f"model {name!r} is not installed. Installed: {known}. "
            f"Pull it with: ollama pull {name}"
        )
        self.name = name
        self.installed = installed


class BoundModel:
    """One model, ready to be called. Satisfies the router's `Completion` port
    and the generation path's, so neither imports this module."""

    def __init__(self, client: OllamaClient, model: ModelSettings) -> None:
        self._client = client
        self._model = model

    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any] | None = None
    ) -> str:
        return await self._client.chat(self._model, messages, schema=schema)

    async def describe(self, prompt: str, image: bytes) -> str:
        """One frame and a question about it. Satisfies the vision port.

        The image is base64 in the request body and nowhere else. It is not
        written to a temporary file on the way -- unlike audio, which whisper
        can only read from a path -- so a frame exists in this process and in
        Ollama's, and then it does not exist.
        """
        return await self._client.chat(
            self._model,
            [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64encode(image).decode("ascii")],
                }
            ],
        )


class OllamaClient:
    def __init__(
        self,
        settings: OllamaSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        # Injected in tests, so the suite never needs Ollama or a network.
        self._transport = transport

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._settings.host, timeout=timeout, transport=self._transport
        )

    async def installed(self) -> list[str]:
        """The models Ollama actually has, for error messages worth reading."""
        async with self._client(timeout=5.0) as client:
            try:
                response = await client.get("/api/tags")
            except httpx.ConnectError as error:
                raise OllamaUnavailable(self._settings.host) from error

            response.raise_for_status()
            payload = response.json()

        return sorted(str(model["name"]) for model in payload.get("models", []))

    async def chat(
        self,
        model: ModelSettings,
        messages: list[dict[str, Any]],
        *,
        schema: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        """One non-streaming turn. Returns the message content, unparsed.

        Not streamed: a routing answer is ~60 tokens of JSON that nothing can
        act on until it is complete. The generation path gains streaming when
        something exists that can render a partial answer.
        """
        payload: dict[str, Any] = {
            "model": model.name,
            "messages": messages,
            "stream": False,
            "think": model.think,
            "keep_alive": model.keep_alive,
        }
        if schema is not None:
            payload["format"] = schema
        if options:
            payload["options"] = options

        async with self._client(timeout=model.timeout) as client:
            try:
                response = await client.post("/api/chat", json=payload)
            except httpx.ConnectError as error:
                raise OllamaUnavailable(self._settings.host) from error
            except httpx.TimeoutException as error:
                raise TimeoutError(f"{model.name} did not answer in time") from error

            if response.status_code == httpx.codes.NOT_FOUND:
                raise ModelMissing(model.name, await self.installed())

            if response.status_code >= httpx.codes.BAD_REQUEST:
                raise OllamaError(
                    f"ollama returned {response.status_code}: {response.text.strip()}"
                )

            body = response.json()

        content = body.get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise OllamaError("ollama returned a message without text content")

        return content

    def bind(self, role: Role) -> BoundModel:
        """The model configured for a role, as a callable collaborator."""
        return BoundModel(self, self._settings.for_role(role))
