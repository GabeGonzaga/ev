"""The composition root and the phase 0 interface.

Everything is wired here and nowhere else: the layers below take their
collaborators as arguments and never reach for a global. That is what makes
the suite able to build the same object graph with a temporary database and a
fake confirmation surface.

    python -m ev.cli "open github.com"
    python -m ev.cli --repl
    python -m ev.cli --specs
    python -m ev.cli --manifest
    python -m ev.cli --serve                       the daemon
    python -m ev.cli --connect "abre example.com"  a turn through it
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import signal
import sqlite3
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ev.application.applications import DEFAULT as DEFAULT_LEVEL
from ev.application.applications import (
    ApplicationLedger,
    applications_path,
    load_levels,
    save_levels,
)
from ev.application.applications import key as application_key
from ev.application.applications import reloader as level_reloader
from ev.application.assistant import Assistant
from ev.application.confirmation import ConfirmationRequest
from ev.application.frames import Frames
from ev.application.policy import ConfidencePolicy, PermissionLedger, PermissionPolicy
from ev.application.speech import Speaker
from ev.application.wake import WakeWord, hear
from ev.capabilities.applications.adapters import ApplicationAdapter
from ev.capabilities.applications.service import ApplicationService
from ev.capabilities.applications.tools import application_tools
from ev.capabilities.browser.adapters import OpenAdapter
from ev.capabilities.browser.service import BrowserService
from ev.capabilities.browser.tools import browser_tools
from ev.capabilities.language.service import LanguageService
from ev.capabilities.language.tools import language_tools
from ev.capabilities.macros.service import MacroService
from ev.capabilities.macros.tools import macro_tools
from ev.capabilities.music.adapters import MusicAdapter
from ev.capabilities.music.service import MusicService
from ev.capabilities.music.tools import music_tools
from ev.capabilities.notes.adapters import NotesAdapter
from ev.capabilities.notes.service import NotesService
from ev.capabilities.notes.tools import notes_tools
from ev.capabilities.reminders.adapters import RemindersAdapter
from ev.capabilities.reminders.service import RemindersService
from ev.capabilities.reminders.tools import reminders_tools
from ev.capabilities.vision.service import LOOK, Vision, VisionService
from ev.capabilities.vision.tools import vision_tools
from ev.domain.access import AccessLevel, Assurance
from ev.domain.journal import JournalEntry
from ev.domain.macro import Macro
from ev.domain.naming import closest
from ev.domain.results import Clarification, ToolResult
from ev.infrastructure.database.connection import connect, default_database_path
from ev.infrastructure.database.journal import SqliteJournal
from ev.infrastructure.database.migrations import migrate
from ev.infrastructure.ipc.client import DaemonRefused, DaemonUnavailable, IpcClient
from ev.infrastructure.ipc.server import IpcServer, SessionConfirmation, socket_path
from ev.infrastructure.macos.applescript import AppleScriptClient
from ev.infrastructure.macos.applications import Applications
from ev.infrastructure.macos.processes import ProcessRunner
from ev.infrastructure.macros import load_macros, macros_path
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
    reloader,
    save_grants,
)
from ev.infrastructure.speech.recognizer import WAKE_MODEL, WhisperCppRecognizer
from ev.infrastructure.speech.synthesizer import SaySynthesizer, SpeechSynthesizer
from ev.infrastructure.wake import load_wake, save_wake, wake_path
from ev.infrastructure.wake import reloader as reloader_for_wake
from ev.infrastructure.web.server import DEFAULT_PORT, WebSurface
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

    def __init__(
        self, remember: Callable[[str, AccessLevel], None] | None = None
    ) -> None:
        self._interactive = sys.stdin.isatty()
        self._remember = remember

    async def confirm(self, request: ConfirmationRequest) -> bool:
        detail = ", ".join(f"{key}={value}" for key, value in request.arguments.items())
        print(f"{request.tool} ({request.risk.value}) {detail}", file=sys.stderr)

        if request.assurance not in {Assurance.NONE, Assurance.ACK}:
            # A click is not a password. A terminal cannot raise the system's
            # own dialog, and substituting a weaker answer for a stronger one
            # is the whole failure this exists to prevent.
            print(
                f"{request.application or request.tool} is set to "
                f"{request.assurance.value}, which only the app can satisfy. "
                f"Open E.V. and ask there, or lower it: "
                f"ev --app '{request.application}' ask",
                file=sys.stderr,
            )
            return False

        if not self._interactive:
            print("declined: not a terminal", file=sys.stderr)
            return False

        # input() blocks the loop, which is correct here: there is nothing else
        # for E.V. to do while it waits for the person in front of it.
        prompt = "run it? [y]es / [n]o"
        if request.application:
            prompt += " / [a]lways / ne[v]er"
        answered = input(f"{prompt} ").strip().casefold()

        if request.application and self._remember is not None:
            # The terminal could only ever say yes or no, so the only way to
            # stop being asked was to go and edit a file. "Always" and "never"
            # belong wherever the question is put.
            if answered in {"a", "always", "sempre"}:
                self._remember(request.application, AccessLevel.OPEN)
                return True
            if answered in {"v", "never", "nunca"}:
                self._remember(request.application, AccessLevel.BLOCKED)
                return False

        return answered in {"y", "yes", "s", "sim"}


class _NoVision:
    """For the paths that build a registry without a model.

    A tool that cannot see must say so rather than describing a room it
    imagined -- the same reasoning as `_NoModel` below.
    """

    async def describe(self, prompt: str, image: bytes) -> str:  # pragma: no cover
        raise AssertionError("this path has no vision model")


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
    access: ApplicationLedger
    settings: OllamaSettings
    speaker: Speaker
    frames: Frames

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
    access: ApplicationLedger,
    generation: Completion,
    speaker: Speaker,
    frames: Frames,
    vision: Vision,
    macros: Path | None = None,
    artwork: Path | None = None,
) -> Registry:
    registry = Registry(
        policy=PermissionPolicy(ledger, applications=access),
        confirmation=confirmation,
        journal=journal,
    )

    processes = ProcessRunner()
    # Every Apple Event is evidence: one delivered proves Automation is on, and
    # one refused proves it is off. Better evidence than anyone typing --grant.
    applescript = AppleScriptClient(processes, report=ledger.update)

    def saved() -> dict[str, Macro]:
        # Read per run rather than held: a macro edited in an editor should
        # work on the next turn, the same reason grants are re-read.
        if macros is None:
            return {}
        try:
            return load_macros(macros)
        except ValueError:
            # A broken file is reported by `ev --macros`, and must not stop
            # every other tool from working.
            return {}

    applications = Applications()

    for spec in (
        *browser_tools(BrowserService(OpenAdapter(processes), speaker)),
        *application_tools(
            ApplicationService(
                ApplicationAdapter(processes, applescript), applications, speaker
            ),
            applications,
        ),
        *music_tools(MusicService(MusicAdapter(applescript), speaker, artwork)),
        *notes_tools(NotesService(NotesAdapter(applescript), speaker)),
        *reminders_tools(RemindersService(RemindersAdapter(applescript), speaker)),
        *language_tools(LanguageService(generation)),
        # The frame is bound by whichever surface captured it, before the turn.
        # Nothing in the tool selects an image (invariant 8).
        *vision_tools(VisionService(frames, vision, speaker)),
        # A macro calls the registry it lives in: same door, once per step.
        *macro_tools(MacroService(saved, registry.call, speaker)),
    ):
        registry.register(spec)

    return registry


def build(
    *,
    database: Path | None,
    confirmation: ConfirmationPort | None = None,
    model: str | None = None,
    completion: Completion | None = None,
    speaker: Speaker | None = None,
    vision: Vision | None = None,
) -> Application:
    connection: sqlite3.Connection | None = None
    journal: JournalPort
    settings = OllamaSettings()

    if database is None:
        journal = RefusingJournal()
        ledger = PermissionLedger()
        access = ApplicationLedger()
    else:
        connection = connect(database)
        migrate(connection)
        journal = SqliteJournal(connection)
        # E.V. keeps its state in one directory; the grants and the model
        # settings sit beside the journal rather than behind more path flags.
        grants = grants_path(database.parent)
        ledger = PermissionLedger(
            load_grants(grants),
            refresh=reloader(grants),
            # What macOS answers is written down, so the next run starts
            # knowing it. Only grants: a refusal is undone in System Settings
            # at any moment, and one on disk would outlive the decision.
            persist=lambda granted: save_grants(grants, sorted(granted)),
        )
        settings = load_settings(settings_path(database.parent))
        levels = applications_path(database.parent)
        access = ApplicationLedger(
            load_levels(levels),
            refresh=level_reloader(levels),
            persist=lambda known: save_levels(levels, known),
        )

    if model is not None:
        settings = settings.with_model(model)

    # Injected in tests; otherwise the model configured for each role. One
    # client, both paths, as CLAUDE.md requires.
    client = None if completion is not None else OllamaClient(settings)
    router_model: Completion = completion or client.bind("router")  # type: ignore[union-attr]
    generation_model: Completion = completion or client.bind("generation")  # type: ignore[union-attr]

    voice = speaker or Speaker()
    frames = Frames()
    # Not a `Completion`: a model that sees takes an image, and the vision role
    # is loaded per capture rather than held resident.
    eyes: Vision
    if vision is not None:
        eyes = vision
    elif client is not None:
        eyes = client.bind("vision")
    else:
        eyes = _NoVision()
    registry = build_registry(
        journal=journal,
        confirmation=confirmation or ConsoleConfirmation(access.remember),
        ledger=ledger,
        access=access,
        generation=generation_model,
        speaker=voice,
        frames=frames,
        vision=eyes,
        macros=macros_path(database.parent) if database is not None else None,
        # Beside the journal, and overwritten: one cover at a time, and never
        # in the repository.
        artwork=(database.parent / "artwork.bin") if database is not None else None,
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
        access=access,
        settings=settings,
        speaker=voice,
        frames=frames,
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


async def turn(
    application: Application,
    utterance: str,
    voice: SpeechSynthesizer | None = None,
    locale: str | None = None,
) -> int:
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
        spoken = render_clarification(outcome)
        print(spoken, file=sys.stderr)
        if voice is not None:
            # A question is worth hearing; it is the one the user must answer.
            await voice.speak(outcome.response or spoken, voice=locale)
        return EXIT_UNSURE

    if voice is not None and outcome.speech:
        await voice.speak(outcome.speech, voice=locale)

    if outcome.ok:
        print(render(outcome))
        return EXIT_OK

    print(render(outcome), file=sys.stderr)
    return EXIT_FAILED


async def repl(
    application: Application,
    voice: SpeechSynthesizer | None = None,
    locale: str | None = None,
) -> int:
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

        await turn(application, utterance, voice, locale)


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
        "--wake",
        nargs="?",
        const="",
        default=None,
        metavar="WORD",
        help="the name E.V. answers to. `--wake` shows it, `--wake jarvis` "
        "sets it, `--wake off` and `--wake on` stop and start listening",
    )
    parser.add_argument(
        "--also",
        action="append",
        default=None,
        metavar="SPELLING",
        help="another way the microphone writes the name, e.g. --also evie",
    )
    parser.add_argument(
        "--apps",
        action="store_true",
        help="what E.V. may do with each application on this Mac",
    )
    parser.add_argument(
        "--app",
        nargs=2,
        metavar=("NAME", "LEVEL"),
        default=None,
        help="set one: open (act freely), ask (every time), verify (macOS asks "
        "for you), blocked (never)",
    )
    parser.add_argument(
        "--macros",
        action="store_true",
        help="list the saved macros and check them against the tools that "
        "exist, before one of them fails halfway through",
    )
    parser.add_argument(
        "--history",
        nargs="?",
        type=int,
        const=20,
        default=None,
        metavar="N",
        help="what E.V. has done, newest first",
    )
    parser.add_argument(
        "--find",
        default=None,
        metavar="TEXT",
        help="search what E.V. has done: a tool, an album, a note's title. "
        "Accents are folded, so 'marco' finds 'Março'.",
    )
    parser.add_argument(
        "--locale",
        default=None,
        metavar="TAG",
        help="the session locale, e.g. pt-PT. It chooses the voice and is "
        "carried to the daemon. It never touches the utterance: translating "
        "before routing would mistranslate the arguments.",
    )
    parser.add_argument(
        "--speak",
        action="store_true",
        help="say the answer out loud, with the pt-PT voice when the locale "
        "asks for it. Development TTS: the native host speaks in the app.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="run the daemon: one warm core, several clients, on a Unix socket "
        "beside the journal. A cold model costs 7.5 s; this pays it once.",
    )
    parser.add_argument(
        "--web",
        nargs="?",
        type=int,
        const=DEFAULT_PORT,
        default=None,
        metavar="PORT",
        help="also serve the panel to this machine's browser, on loopback, "
        "with a token. Off unless asked for: a surface that always exists is "
        "one an attacker can rely on.",
    )
    parser.add_argument(
        "--connect",
        action="store_true",
        help="send the utterance to a running daemon instead of starting a core",
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

    if args.find is not None:
        return await show_history(database, args.history or 20, search=args.find)

    if args.history is not None:
        return await show_history(database, args.history)

    if args.wake is not None or args.also is not None:
        return set_wake(database.parent, args.wake, args.also or [])

    if args.app is not None:
        return set_level(database.parent, args.app[0], args.app[1])

    if args.apps:
        return show_applications(database.parent)

    if args.macros:
        application = build(database=database, completion=_NoModel())
        try:
            return show_macros(database, application.registry)
        finally:
            await application.aclose()

    if args.connect:
        return await connected(database.parent, args)

    if args.serve:
        return await serve(
            database=database,
            model=args.model,
            completion=completion,
            web_port=args.web,
        )

    application = build(database=database, model=args.model, completion=completion)
    application.speaker.bind(args.locale)
    voice = SaySynthesizer(ProcessRunner()) if args.speak else None
    try:
        if args.repl:
            return await repl(application, voice, args.locale)

        utterance = " ".join(args.utterance).strip()
        if not utterance:
            print("nothing to do. Try --repl or an utterance.", file=sys.stderr)
            return EXIT_NOT_UNDERSTOOD

        return await turn(application, utterance, voice, args.locale)
    finally:
        await application.aclose()


def show_macros(database: Path, registry: Registry) -> int:
    """List the macros, and validate them against the tools that exist.

    A macro is checked here rather than when it runs, because a list of calls
    that fails at step four is a trap and this is the moment to find it.
    """
    path = macros_path(database.parent)

    try:
        macros = load_macros(path)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return EXIT_FAILED

    if not macros:
        print(f"no macros. Write some in {path}", file=sys.stderr)
        return EXIT_OK

    broken = 0
    for macro in sorted(macros.values(), key=lambda m: m.name):
        print(f"{macro.name}  (v{macro.version})  {macro.description}".rstrip())

        for number, step in enumerate(macro.steps, start=1):
            spec = registry.spec(step.tool)
            if spec is None:
                print(f"  {number}. {step.tool}  <- no such tool", file=sys.stderr)
                broken += 1
                continue

            try:
                spec.args.model_validate(step.arguments)
            except ValidationError as error:
                first = error.errors()[0]
                where = ".".join(str(part) for part in first["loc"]) or "(root)"
                print(
                    f"  {number}. {step.tool}  <- {where}: {first['msg']}",
                    file=sys.stderr,
                )
                broken += 1
            else:
                print(f"  {number}. {step.tool} {step.arguments}")

    return EXIT_FAILED if broken else EXIT_OK


def set_wake(state_dir: Path, word: str | None, also: list[str]) -> int:
    """Show the name, change it, or start and stop listening for it."""
    path = wake_path(state_dir)
    try:
        wake = load_wake(path)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return EXIT_FAILED

    if word in {"on", "off"}:
        wake = WakeWord(word=wake.word, also=wake.also, enabled=word == "on")
    elif word:
        # A new name is a new name: the old spellings belonged to the old one.
        wake = WakeWord(word=word, also=tuple(also), enabled=wake.enabled)
    elif also:
        wake = WakeWord(
            word=wake.word, also=tuple([*wake.also, *also]), enabled=wake.enabled
        )

    if word is not None or also:
        save_wake(path, wake)

    spelled = ", ".join(sorted(wake.variants()))
    print(f"name: {wake.word}")
    print(f"heard as: {spelled}")
    print("listening" if wake.enabled else "not listening (ev --wake on)")
    if wake.enabled:
        # Said plainly, because it is the whole of what the feature costs.
        print(
            "while it listens, speech near this Mac is transcribed on it to "
            "check for the name. Nothing leaves, and nothing that was not "
            "addressed to E.V. is recorded."
        )
    return EXIT_OK


def set_level(state_dir: Path, name: str, level: str) -> int:
    """Say what E.V. may do with one application."""
    try:
        wanted = AccessLevel(level)
    except ValueError:
        known = ", ".join(item.value for item in AccessLevel)
        print(f"unknown level {level!r}. Known: {known}", file=sys.stderr)
        return EXIT_FAILED

    installed = Applications().installed()
    # Matched against what is here, so a typo is caught now rather than
    # becoming a level that silently applies to nothing.
    matched = closest(name, installed) if installed else name
    if matched is None:
        print(f"no application called {name!r} on this Mac", file=sys.stderr)
        return EXIT_FAILED

    path = applications_path(state_dir)
    levels = load_levels(path)
    levels[application_key(matched)] = wanted
    save_levels(path, levels)

    print(f"{matched}: {wanted.value}")
    return EXIT_OK


def show_applications(state_dir: Path) -> int:
    """What has been decided, and what has not.

    Everything installed is listed, because a control you have to remember to
    look for is one nobody looks for.
    """
    levels = load_levels(applications_path(state_dir))
    installed = Applications().installed()

    for name in installed:
        level = levels.get(application_key(name))
        mark = level.value if level is not None else f"{DEFAULT_LEVEL.value} (default)"
        print(f"{name:<34} {mark}")

    known = {application_key(name) for name in installed}
    for name, level in sorted(levels.items()):
        # A level for something that is not installed any more: worth showing
        # rather than silently dropping, because it will start applying again
        # the day it is reinstalled.
        if name not in known:
            print(f"{name:<34} {level.value} (not installed)")

    return EXIT_OK


async def show_history(database: Path, limit: int, *, search: str | None = None) -> int:
    """The trail, read back. The same rows the UI will show in phase 3."""
    application = build(database=database, completion=_NoModel())
    try:
        journal = application.journal
        if not isinstance(journal, SqliteJournal):  # pragma: no cover
            return EXIT_FAILED

        entries = (
            await journal.search(search, limit=limit)
            if search is not None
            else await journal.recent(limit=limit)
        )
        if not entries:
            # A search that found nothing is not the same as a journal with
            # nothing in it, and someone who typed a word wants to know which
            # of the two happened.
            print(
                f"nothing matches {search!r}." if search else "nothing yet.",
                file=sys.stderr,
            )
            return EXIT_OK

        for entry in entries:
            mark = "ok " if entry.ok else "FAIL"
            detail = entry.speech or (entry.error_message or "")
            print(f"{entry.recorded_at}  {mark}  {entry.tool:<20} {detail}")
        return EXIT_OK
    finally:
        await application.aclose()


class _NoModel:
    """Reading history asks nothing of a model, so nothing here should reach
    one -- and if something does, it should say so rather than start Ollama."""

    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any]
    ) -> str:  # pragma: no cover
        raise AssertionError("reading history must not call a model")


async def serve(
    *,
    database: Path,
    model: str | None,
    completion: Completion | None,
    web_port: int | None = None,
) -> int:
    """Run until interrupted.

    The registry is built once and outlives every client, so its confirmation
    port follows whoever is currently asking rather than being a terminal.
    """
    # Built before the application, and told where to report a verification
    # once there is somewhere to report it to.
    confirmation = SessionConfirmation()
    turns = asyncio.Lock()
    application = build(
        database=database, confirmation=confirmation, model=model, completion=completion
    )
    confirmation.observe(application.access.verified)
    # The recogniser is spawned per utterance rather than held resident:
    # CLAUDE.md does not hold the LLM and the STT model in memory at once, and
    # the measured cost of that choice is in the latency table.
    recognizer = WhisperCppRecognizer(ProcessRunner())

    async def transcribe(audio: Path, locale: str) -> str:
        return await recognizer.transcribe(audio, language=locale)

    # Two recognisers, two jobs. `tiny` decides whether two syllables were the
    # name, on every burst of speech in the room; `small` hears the request
    # that follows, once.
    listener = WhisperCppRecognizer(ProcessRunner(), model=WAKE_MODEL)
    heard_name = reloader_for_wake(wake_path(database.parent))
    known = load_wake(wake_path(database.parent))

    async def woken(audio: Path, locale: str) -> str | None:
        """Was that E.V.'s name, and what followed it.

        `None` is the answer almost every time, and it is the important one:
        nothing runs, nothing is journalled, nothing is emitted. Room audio
        that was not addressed to E.V. leaves no trace of having been heard.

        Heard by `tiny`, not by `small`: this runs on every burst of speech in
        the room rather than once per request, and what it gets wrong is
        caught by a string comparison rather than by the model.
        """
        nonlocal known
        known = heard_name() or known
        if not known.enabled:
            return None

        said = await listener.transcribe(audio, language=locale)
        heard = hear(said, known)
        return heard.rest if heard.woke else None

    async def handle(text: str, locale: str | None = None) -> object:
        # Bound per turn, under the same lock that serialises turns, for the
        # same reason the confirmation port is: one core, many surfaces, and
        # the language belongs to whoever is speaking now.
        application.speaker.bind(locale)
        return await application.assistant.handle(text)

    async def look(
        image: bytes, text: str | None, locale: str | None
    ) -> ToolResult | Clarification | None:
        """A frame, bound for one turn.

        With words, it is an ordinary turn that happens to have something to
        look at -- the router may or may not reach for the camera. Without
        them, pressing Look is the request, and it goes straight to the tool
        rather than through a sentence nobody said.
        """
        application.speaker.bind(locale)
        application.frames.bind(image)
        try:
            if text:
                return await application.assistant.handle(text)
            return await application.registry.call(LOOK, {})
        finally:
            # Invariant 8: frames are not persisted. Not to disk, and not in
            # memory past the turn that asked about them.
            application.frames.clear()

    async def history(
        limit: int, before: int | None, query: str | None = None
    ) -> list[JournalEntry]:
        journal = application.journal
        if not isinstance(journal, SqliteJournal):  # pragma: no cover
            return []
        if query:
            return await journal.search(query, limit=limit)
        return await journal.recent(limit=limit, before=before)

    server = IpcServer(
        path=socket_path(database.parent),
        handle=handle,  # type: ignore[arg-type]
        confirmation=confirmation,
        transcribe=transcribe,
        wake=woken,
        look=look,
        # The host is the only process macOS answers about the microphone and
        # the camera, so it is the only one that can say (invariant 7).
        report=application.ledger.update,
        # "Always" and "never", from whoever was asked.
        remember=application.access.remember,
        history=history,
        on_close=application.aclose,
        turn_lock=turns,
    )

    try:
        await server.start()
    except OSError as error:
        print(str(error), file=sys.stderr)
        await application.aclose()
        return EXIT_FAILED

    surface: WebSurface | None = None
    if web_port is not None:
        surface = WebSurface(
            state_dir=database.parent,
            handle=handle,  # type: ignore[arg-type]
            history=history,
            transcribe=transcribe,
            look=look,
            remember=application.access.remember,
            assets=Path(__file__).resolve().parents[1] / "ui" / "dist",
            port=web_port,
            # The same confirmation port and the same lock as the socket: one
            # core, one turn at a time, and one person being asked.
            confirmation=confirmation,
            turn_lock=turns,
        )
        try:
            await surface.start()
        except OSError as error:
            print(f"could not serve the panel: {error}", file=sys.stderr)
            await application.aclose()
            return EXIT_FAILED

        # The token rides in the fragment, so it never reaches a server log or
        # a Referer header. Printed once, here, for the person who asked.
        print(f"panel at {surface.url()}", file=sys.stderr)

    print(f"listening on {socket_path(database.parent)}", file=sys.stderr)

    # A daemon is stopped by a signal, not by Ctrl-C in a terminal. Without
    # this, SIGTERM kills the process between a turn and the journal flush,
    # and the action that just ran is never recorded -- which ADR 0004 calls a
    # defect rather than an inconvenience.
    loop = asyncio.get_running_loop()
    stopping = asyncio.Event()
    for name in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(name, stopping.set)

    serving = asyncio.create_task(server.serve_forever())
    try:
        await asyncio.wait(
            [serving, asyncio.create_task(stopping.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        serving.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serving
        if surface is not None:
            await surface.aclose()
        await server.aclose()

    return EXIT_OK


def _ask_on_terminal(event: dict[str, Any]) -> bool:
    arguments = dict(event.get("arguments", {}))
    detail = ", ".join(f"{key}={value}" for key, value in arguments.items())
    print(f"{event['tool']} ({event['risk']}) {detail}", file=sys.stderr)

    if not sys.stdin.isatty():
        print("declined: not a terminal", file=sys.stderr)
        return False

    return input("run it? [y/N] ").strip().casefold() in {"y", "yes", "s", "sim"}


async def connected(state_dir: Path, args: argparse.Namespace) -> int:
    """One turn through a running daemon, which already has the model loaded."""
    utterance = " ".join(args.utterance).strip()
    if not utterance:
        print("nothing to do. Try an utterance.", file=sys.stderr)
        return EXIT_NOT_UNDERSTOOD

    try:
        async with IpcClient(socket_path(state_dir)) as client:
            response, events = await client.submit(
                utterance, locale=args.locale, ask=_ask_on_terminal
            )
    except (DaemonUnavailable, DaemonRefused) as error:
        print(str(error), file=sys.stderr)
        return EXIT_UNAVAILABLE

    for event in events:
        # speech.requested is the daemon asking for a sentence to be spoken.
        # On a terminal, printing it is what speaking means.
        if event.get("type") == "speech.requested":
            print(event["text"])

    payload = dict(response.get("payload", {}))
    outcome = payload.get("outcome")

    if outcome == "not_understood":
        print("I did not understand that.", file=sys.stderr)
        return EXIT_NOT_UNDERSTOOD
    if outcome == "unsure":
        return EXIT_UNSURE
    return EXIT_OK if payload.get("ok") else EXIT_FAILED


def main(
    argv: Sequence[str] | None = None, completion: Completion | None = None
) -> int:
    # `completion` is the composition root's job: the suite supplies a fake
    # model so no test ever reaches a real one.
    return asyncio.run(run(parse_args(argv), completion))


if __name__ == "__main__":
    raise SystemExit(main())
