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
from ev.application.policy import ConfidencePolicy, PermissionLedger, PermissionPolicy
from ev.capabilities.browser.adapters import OpenAdapter
from ev.capabilities.browser.service import BrowserService
from ev.capabilities.browser.tools import browser_tools
from ev.capabilities.language.service import LanguageService
from ev.capabilities.language.tools import language_tools
from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.service import MusicService
from ev.capabilities.music.tools import music_tools
from ev.domain.results import Clarification, ToolResult
from ev.infrastructure.database.connection import connect, default_database_path
from ev.infrastructure.database.journal import SqliteJournal
from ev.infrastructure.database.migrations import migrate
from ev.infrastructure.macos.applescript import AppleScriptClient
from ev.infrastructure.macos.processes import ProcessRunner
from ev.infrastructure.ollama.client import OllamaClient, OllamaError
from ev.infrastructure.ollama.settings import (
    OllamaSettings,
    load_settings,
    settings_path,
)
from ev.infrastructure.permissions import (
    grants_path,
    load_grants,
    parse_permission,
    save_grants,
)
from ev.registry import CallRecord, ConfirmationPort, JournalPort, Registry
from ev.router.model import Completion, ModelRouter
from ev.router.static import StaticRouter

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_NOT_UNDERSTOOD = 2
EXIT_UNSURE = 3
"""A guess E.V. would not act on. Distinct from 2: something was understood."""

EXIT_UNAVAILABLE = 4
"""Ollama is not answering. An operational fault, not a failure to understand."""


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
    settings: OllamaSettings

    async def aclose(self) -> None:
        # The journal batches, so the pending tail is only durable once this
        # runs. Every exit path goes through it.
        if isinstance(self.journal, SqliteJournal):
            await self.journal.flush()
        if self.connection is not None:
            self.connection.close()


def build_registry(
    *,
    journal: JournalPort,
    confirmation: ConfirmationPort,
    ledger: PermissionLedger,
    generation: Completion,
) -> Registry:
    registry = Registry(
        policy=PermissionPolicy(ledger), confirmation=confirmation, journal=journal
    )

    processes = ProcessRunner()
    applescript = AppleScriptClient(processes)

    for spec in (
        *browser_tools(BrowserService(OpenAdapter(processes))),
        *music_tools(MusicService(MusicAdapter(applescript))),
        *language_tools(LanguageService(generation)),
    ):
        registry.register(spec)

    return registry


def build(
    *,
    database: Path | None,
    confirmation: ConfirmationPort | None = None,
    model: str | None = None,
    completion: Completion | None = None,
) -> Application:
    connection: sqlite3.Connection | None = None
    journal: JournalPort
    settings = OllamaSettings()

    if database is None:
        journal = RefusingJournal()
        ledger = PermissionLedger()
    else:
        connection = connect(database)
        migrate(connection)
        journal = SqliteJournal(connection)
        # E.V. keeps its state in one directory; the grants and the model
        # settings sit beside the journal rather than behind more path flags.
        ledger = PermissionLedger(load_grants(grants_path(database.parent)))
        settings = load_settings(settings_path(database.parent))

    if model is not None:
        settings = settings.with_model(model)

    # Injected in tests; otherwise the model configured for each role. One
    # client, both paths, as CLAUDE.md requires.
    client = None if completion is not None else OllamaClient(settings)
    router_model: Completion = completion or client.bind("router")  # type: ignore[union-attr]
    generation_model: Completion = completion or client.bind("generation")  # type: ignore[union-attr]

    registry = build_registry(
        journal=journal,
        confirmation=confirmation or ConsoleConfirmation(),
        ledger=ledger,
        generation=generation_model,
    )

    return Application(
        assistant=Assistant(
            StaticRouter(),
            registry,
            model_router=ModelRouter(router_model, registry.specs()),
            confidence=ConfidencePolicy(
                accept_at=settings.routing.accept_at,
                clarify_at=settings.routing.clarify_at,
            ),
        ),
        registry=registry,
        journal=journal,
        connection=connection,
        ledger=ledger,
        settings=settings,
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


def render_clarification(clarification: Clarification) -> str:
    """Ask rather than act.

    The model's own line is preferred when it gave one, because it is in the
    language of the request. The fallback is English, which is a gap the
    language capability closes.
    """
    detail = ", ".join(
        f"{key}={value}" for key, value in clarification.arguments.items()
    )
    guess = f"{clarification.tool}({detail})" if detail else clarification.tool

    if clarification.response:
        return f"{clarification.response} [{guess}, {clarification.confidence:.2f}]"
    return f"Did you mean {guess}? I am only {clarification.confidence:.0%} sure."


def render(result: ToolResult) -> str:
    if result.speech:
        return result.speech
    if result.ok:
        return f"done: {result.tool}"
    return result.error.message if result.error else f"failed: {result.tool}"


async def turn(application: Application, utterance: str) -> int:
    try:
        outcome = await application.assistant.handle(utterance)
    except OllamaError as error:
        # Not a failure to understand: nothing was asked of the model at all.
        print(str(error), file=sys.stderr)
        return EXIT_UNAVAILABLE

    if outcome is None:
        print("I did not understand that.", file=sys.stderr)
        return EXIT_NOT_UNDERSTOOD

    if isinstance(outcome, Clarification):
        print(render_clarification(outcome), file=sys.stderr)
        return EXIT_UNSURE

    if outcome.ok:
        print(render(outcome))
        return EXIT_OK

    print(render(outcome), file=sys.stderr)
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
    parser.add_argument(
        "--model",
        default=None,
        metavar="NAME",
        help="use this model for every role, for this run only. Overrides "
        "models.json, which is where a lasting choice belongs.",
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace, completion: Completion | None = None) -> int:
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

    application = build(database=database, model=args.model, completion=completion)
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


def main(
    argv: Sequence[str] | None = None, completion: Completion | None = None
) -> int:
    # `completion` is the composition root's job: the suite supplies a fake
    # model so no test ever reaches a real one.
    return asyncio.run(run(parse_args(argv), completion))


if __name__ == "__main__":
    raise SystemExit(main())
