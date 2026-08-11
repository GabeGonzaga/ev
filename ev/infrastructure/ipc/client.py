"""Talking to a running daemon instead of starting a core of your own.

This is what stops the socket being a server with an imagined caller. The CLI
uses it, so the handshake, the correlation and the confirmation round trip are
exercised by something real long before Rust exists.

It is not faster than a local core, and measuring said so: 0.258 s against
0.272 s. The client is itself a Python process paying the same startup, and
model residency belongs to Ollama either way (ADR 0016).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from protocol.messages import (
    PROTOCOL_VERSION,
    ConfirmationRespond,
    Hello,
    Request,
    SessionCancel,
    UtteranceSubmit,
)


class DaemonUnavailable(Exception):
    def __init__(self, path: Path) -> None:
        super().__init__(f"no daemon at {path}. Start one with: ev --serve")
        self.path = path


class DaemonRefused(Exception):
    """The daemon answered, and said no. A version mismatch usually."""


Ask = Callable[[dict[str, Any]], bool]
"""How to answer a confirmation.required. The client does not decide."""


class IpcClient:
    def __init__(self, path: Path, *, protocol: str = PROTOCOL_VERSION) -> None:
        self._path = path
        # A parameter so a client claiming another version can be exercised.
        # The daemon refuses it, which is the behaviour worth a test.
        self._protocol = protocol
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def __aenter__(self) -> IpcClient:
        try:
            self._reader, self._writer = await asyncio.open_unix_connection(
                str(self._path)
            )
        except (FileNotFoundError, ConnectionRefusedError) as error:
            raise DaemonUnavailable(self._path) from error

        await self._handshake()
        return self

    async def __aexit__(self, *exception: object) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    async def _handshake(self) -> None:
        response = await self._send(Hello(protocol=self._protocol, client="ev.cli"))
        if not response.get("ok"):
            error = response.get("error") or {}
            raise DaemonRefused(str(error.get("message", "refused")))

    async def _write(self, request: Request) -> None:
        assert self._writer is not None
        self._writer.write(request.model_dump_json().encode() + b"\n")
        await self._writer.drain()

    async def _read(self) -> dict[str, Any]:
        assert self._reader is not None
        line = await self._reader.readline()
        if not line:
            raise DaemonUnavailable(self._path)
        parsed: dict[str, Any] = json.loads(line)
        return parsed

    async def _send(self, command: Any) -> dict[str, Any]:
        """Send one command and read until its response. Anything else on the
        way is an event, and events are not answers."""
        identifier = uuid.uuid4().hex
        await self._write(Request(id=identifier, command=command))

        while True:
            message = await self._read()
            if message.get("id") == identifier:
                return message

    async def submit(
        self, text: str, *, locale: str | None = None, ask: Ask | None = None
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """One turn. Returns its response and every event it produced.

        A confirmation arrives mid-turn as an event, and the answer goes back
        as its own command: the turn on the far side is blocked until it does.
        """
        identifier = uuid.uuid4().hex
        await self._write(
            Request(id=identifier, command=UtteranceSubmit(text=text, locale=locale))
        )

        events: list[dict[str, Any]] = []
        while True:
            message = await self._read()

            if message.get("id") == identifier:
                return message, events

            events.append(message)

            if message.get("type") == "confirmation.required":
                granted = bool(ask(message)) if ask is not None else False
                await self._write(
                    Request(
                        id=uuid.uuid4().hex,
                        command=ConfirmationRespond(
                            request=str(message["id"]), granted=granted
                        ),
                    )
                )

    async def cancel(self) -> None:
        await self._send(SessionCancel())
