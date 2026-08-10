"""The composition root and the phase 0 interface.

Everything is wired here and nowhere else: the layers below take their
collaborators as arguments and never reach for a global. That is what makes
the suite able to build the same object graph with a temporary database and a
fake confirmation surface.

    python -m ev.cli "open github.com"
    python -m ev.cli --repl
    python -m ev.cli --specs
    python -m ev.cli --manifest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ev.application.assistant import Assistant
from ev.application.confirmation import ConfirmationRequest
from ev.application.policy import PermissionLedger, PermissionPolicy
from ev.capabilities.browser.adapters import OpenAdapter
from ev.capabilities.browser.service import BrowserService
from ev.capabilities.browser.tools import browser_tools
from ev.domain.results import ToolResult
from ev.infrastructure.database.connection import connect, default_database_path
from ev.infrastructure.database.journal import SqliteJournal
from ev.infrastructure.database.migrations import migrate
from ev.infrastructure.macos.processes import ProcessRunner
from ev.registry import CallRecord, ConfirmationPort, JournalPort, Registry
from ev.router.static import StaticRouter

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_NOT_UNDERSTOOD = 2


class ConsoleConfirmation:
    """Ask on the terminal. Anything other than an explicit yes is a no.

    A non-interactive stdin declines without asking: a destructive action must
    not be approved by a pipe that happened to be empty.
    """

    def __init__(self) -> None:
        self._interactive = sys.stdin.isatty()

    async def confirm(self, request: ConfirmationRequest) -> bool:
        detail = ", ".join(f"{key}={value}" for key, value in request.arguments.items())
        print(f"{request.tool} ({request.risk.value}) {detail}", file=sys.stderr)

        if not self._interactive:
            print("declined: not a terminal", file=sys.stderr)
            return False

        # input() blocks the loop, which is correct here: there is nothing else
        # for E.V. to do while it waits for the person in front of it.
        return input("run it? [y/N] ").strip().casefold() in {"y", "yes", "s", "sim"}


class RefusingJournal:
    """For the read-only paths. Nothing there should reach a tool, so a call
    is a bug rather than something to record quietly."""

    async def record(self, record: CallRecord) -> None:  # pragma: no cover
        raise AssertionError("this path must not execute tools")


@dataclass
class Application:
    assistant: Assistant
    registry: Registry
    journal: JournalPort
    connection: sqlite3.Connection | None

    async def aclose(self) -> None:
        # The journal batches, so the pending tail is only durable once this
        # runs. Every exit path goes through it.
        if isinstance(self.journal, SqliteJournal):
            await self.journal.flush()
        if self.connection is not None:
            self.connection.close()


def build_registry(
    *, journal: JournalPort, confirmation: ConfirmationPort, ledger: PermissionLedger
) -> Registry:
    registry = Registry(
        policy=PermissionPolicy(ledger), confirmation=confirmation, journal=journal
    )

    processes = ProcessRunner()
    for spec in browser_tools(BrowserService(OpenAdapter(processes))):
        registry.register(spec)

    return registry


def build(
    *, database: Path | None, confirmation: ConfirmationPort | None = None
) -> Application:
    connection: sqlite3.Connection | None = None
    journal: JournalPort

    if database is None:
        journal = RefusingJournal()
    else:
        connection = connect(database)
        migrate(connection)
        journal = SqliteJournal(connection)

    registry = build_registry(
        journal=journal,
        confirmation=confirmation or ConsoleConfirmation(),
        ledger=PermissionLedger(),
    )

    return Application(
        assistant=Assistant(StaticRouter(), registry),
        registry=registry,
        journal=journal,
        connection=connection,
    )


def render(result: ToolResult) -> str:
    if result.speech:
        return result.speech
    if result.ok:
        return f"done: {result.tool}"
    return result.error.message if result.error else f"failed: {result.tool}"


async def turn(application: Application, utterance: str) -> int:
    result = await application.assistant.handle(utterance)

    if result is None:
        print("I did not understand that.", file=sys.stderr)
        return EXIT_NOT_UNDERSTOOD

    if result.ok:
        print(render(result))
        return EXIT_OK

    print(render(result), file=sys.stderr)
    return EXIT_FAILED


async def repl(application: Application) -> int:
    while True:
        try:
            utterance = input("ev> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return EXIT_OK

        if utterance in {"", "exit", "quit"}:
            if utterance:
                return EXIT_OK
            continue

        await turn(application, utterance)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ev", description="E.V., phase 0.")
    parser.add_argument("utterance", nargs="*", help="what to do, in any language")
    parser.add_argument("--repl", action="store_true", help="read utterances in a loop")
    parser.add_argument(
        "--specs", action="store_true", help="the generated LLM tool specs"
    )
    parser.add_argument(
        "--manifest", action="store_true", help="what E.V. can do, by capability"
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help=f"journal database (default: {default_database_path()})",
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    if args.specs or args.manifest:
        # No database: these read the registry and execute nothing.
        registry = build(database=None).registry
        payload: list[dict[str, object]] | dict[str, object] = (
            registry.specs() if args.specs else registry.manifest()
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return EXIT_OK

    application = build(database=args.database or default_database_path())
    try:
        if args.repl:
            return await repl(application)

        utterance = " ".join(args.utterance).strip()
        if not utterance:
            print("nothing to do. Try --repl or an utterance.", file=sys.stderr)
            return EXIT_NOT_UNDERSTOOD

        return await turn(application, utterance)
    finally:
        await application.aclose()


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
