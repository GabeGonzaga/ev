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
from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.service import MusicService
from ev.capabilities.music.tools import music_tools
from ev.domain.results import ToolResult
from ev.infrastructure.database.connection import connect, default_database_path
from ev.infrastructure.database.journal import SqliteJournal
from ev.infrastructure.database.migrations import migrate
from ev.infrastructure.macos.applescript import AppleScriptClient
from ev.infrastructure.macos.processes import ProcessRunner
from ev.infrastructure.permissions import (
    grants_path,
    load_grants,
    parse_permission,
    save_grants,
)
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
    ledger: PermissionLedger

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
    applescript = AppleScriptClient(processes)

    for spec in (
        *browser_tools(BrowserService(OpenAdapter(processes))),
        *music_tools(MusicService(MusicAdapter(applescript))),
    ):
        registry.register(spec)

    return registry


def build(
    *, database: Path | None, confirmation: ConfirmationPort | None = None
) -> Application:
    connection: sqlite3.Connection | None = None
    journal: JournalPort

    if database is None:
        journal = RefusingJournal()
        ledger = PermissionLedger()
    else:
        connection = connect(database)
        migrate(connection)
        journal = SqliteJournal(connection)
        # E.V. keeps its state in one directory; the grants sit beside the
        # journal rather than behind a second path flag.
        ledger = PermissionLedger(load_grants(grants_path(database.parent)))

    registry = build_registry(
        journal=journal,
        confirmation=confirmation or ConsoleConfirmation(),
        ledger=ledger,
    )

    return Application(
        assistant=Assistant(StaticRouter(), registry),
        registry=registry,
        journal=journal,
        connection=connection,
        ledger=ledger,
    )


def update_grants(
    state_dir: Path, granting: Sequence[str], revoking: Sequence[str]
) -> int:
    path = grants_path(state_dir)

    try:
        granted = set(load_grants(path))
        granted |= {parse_permission(name) for name in granting}
        granted -= {parse_permission(name) for name in revoking}
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return EXIT_FAILED

    save_grants(path, granted)

    print(", ".join(sorted(item.value for item in granted)) or "(none)")
    # Said plainly, because the word "grant" invites the wrong conclusion.
    print(
        f"recorded in {path}. This grants nothing: macOS still prompts and can "
        "still refuse. It only stops E.V. refusing first.",
        file=sys.stderr,
    )
    return EXIT_OK


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
    parser.add_argument(
        "--grant",
        action="append",
        default=[],
        metavar="PERMISSION",
        help="record that you have granted a TCC permission to E.V. in System "
        "Settings. This grants nothing by itself; it stops E.V. refusing "
        "before macOS is asked. Repeatable.",
    )
    parser.add_argument(
        "--revoke",
        action="append",
        default=[],
        metavar="PERMISSION",
        help="undo a --grant. Repeatable.",
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

    database = args.database or default_database_path()

    if args.grant or args.revoke:
        return update_grants(database.parent, args.grant, args.revoke)

    application = build(database=database)
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
