"""`make eval`: what a real model actually does, per model, per locale.

Not in CI. It needs weights, it is not deterministic, and a bad number here is
information rather than a broken build.

It answers two questions that came out of building phase 1, both from observed
behaviour rather than theory:

1. Where should the confidence threshold sit? A model was seen inventing a
   `music.play` call and rating it 0.6. This sweeps every threshold and reports
   what each one would have executed and refused.
2. Does translation actually translate? A translation model was seen returning
   its input unchanged while E.V. reported success. An echo is counted as a
   miss here, because here there is a known source and target to compare.

    python -m evals.run                        # the configured model
    python -m evals.run --model qwen3:8b --model llama3.1:8b
    python -m evals.run --only translation
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ev.application.frames import Frames
from ev.application.policy import PermissionLedger
from ev.cli import RefusingJournal, build_registry
from ev.infrastructure.database.connection import default_database_path
from ev.infrastructure.ollama.client import OllamaClient, OllamaError
from ev.infrastructure.ollama.settings import (
    OllamaSettings,
    load_settings,
    settings_path,
)
from ev.registry import Registry
from ev.router.model import ModelRouter

ROOT = Path(__file__).resolve().parent


class NeverConfirms:
    async def confirm(self, request: object) -> bool:  # pragma: no cover
        raise AssertionError("evals route; they do not execute")


def cases(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@dataclass
class RoutingOutcome:
    id: str
    locale: str
    expected: str | None
    got: str | None
    confidence: float
    arguments: dict[str, Any] = field(default_factory=dict)
    args_valid: bool = False
    args_match: bool = False
    seconds: float = 0.0

    @property
    def tool_correct(self) -> bool:
        return self.got == self.expected


@dataclass
class TranslationOutcome:
    id: str
    to: str
    echoed: bool
    claimed_success: bool
    expected_found: bool
    rejected_found: bool
    preserved: bool
    text: str
    seconds: float = 0.0

    @property
    def passed(self) -> bool:
        return (
            not self.echoed
            and self.expected_found
            and not self.rejected_found
            and self.preserved
        )


def _arguments_match(expected: dict[str, Any], got: dict[str, Any]) -> bool:
    """Loose on purpose. A model writing "https://github.com/" for "github.com"
    has understood the request; only the tool's own args model decides whether
    the value is usable, and that is measured separately."""
    for key, value in expected.items():
        actual = got.get(key)
        if actual is None:
            return False
        if str(value).casefold() not in str(actual).casefold():
            return False
    return True


async def route(
    router: ModelRouter, registry: Registry, case: dict[str, Any]
) -> RoutingOutcome:
    started = time.monotonic()
    resolution = await router.resolve(case["utterance"])
    seconds = time.monotonic() - started

    outcome = RoutingOutcome(
        id=case["id"],
        locale=case["locale"],
        expected=case["tool"],
        got=resolution.tool if resolution else None,
        confidence=resolution.confidence if resolution else 0.0,
        arguments=dict(resolution.arguments) if resolution else {},
        seconds=seconds,
    )

    if resolution is not None and resolution.tool in registry:
        spec = registry.tools()[
            [tool.name for tool in registry.tools()].index(resolution.tool)
        ]
        try:
            spec.args.model_validate(resolution.arguments)
            outcome.args_valid = True
        except ValidationError:
            outcome.args_valid = False
        outcome.args_match = _arguments_match(
            case.get("arguments", {}), outcome.arguments
        )

    return outcome


async def translate(client: OllamaClient, case: dict[str, Any]) -> TranslationOutcome:
    from ev.capabilities.language.args import TranslateArgs
    from ev.capabilities.language.service import LanguageService

    service = LanguageService(client.bind("generation"))
    started = time.monotonic()
    result = await service.translate(
        TranslateArgs.model_validate({"text": case["text"], "to": case["to"]})
    )
    seconds = time.monotonic() - started

    text = str(result.data.get("text", ""))
    folded = text.casefold()

    return TranslationOutcome(
        id=case["id"],
        to=case["to"],
        echoed=not result.ok or text.strip() == case["text"].strip(),
        # The dangerous one: input returned unchanged and reported as done.
        claimed_success=result.ok and text.strip() == case["text"].strip(),
        expected_found=any(
            word.casefold() in folded for word in case.get("expect_any", [])
        )
        or not case.get("expect_any"),
        rejected_found=any(
            word.casefold() in folded for word in case.get("reject_any", [])
        ),
        preserved=all(token in text for token in case.get("preserve", [])),
        text=text,
        seconds=seconds,
    )


def sweep(outcomes: Sequence[RoutingOutcome]) -> list[tuple[float, int, int]]:
    """For each candidate threshold: how many right answers it would refuse,
    and how many wrong ones it would execute. The second column is the one
    that matters -- those run without being asked about."""
    rows: list[tuple[float, int, int]] = []
    for step in range(0, 11):
        threshold = step / 10
        refused_right = sum(
            1 for o in outcomes if o.tool_correct and o.got and o.confidence < threshold
        )
        ran_wrong = sum(
            1 for o in outcomes if not o.tool_correct and o.confidence >= threshold
        )
        rows.append((threshold, refused_right, ran_wrong))
    return rows


def report_routing(model: str, outcomes: Sequence[RoutingOutcome]) -> None:
    total = len(outcomes)
    correct = [o for o in outcomes if o.tool_correct]
    declines = [o for o in outcomes if o.expected is None]
    invented = [o for o in declines if o.got is not None]

    print(f"\nrouting · {model} · {total} cases")
    print(f"  tool correct        {len(correct)}/{total}")
    for locale in sorted({o.locale for o in outcomes}):
        subset = [o for o in outcomes if o.locale == locale]
        hits = sum(1 for o in subset if o.tool_correct)
        print(f"    {locale:<16}{hits}/{len(subset)}")

    routed = [o for o in outcomes if o.got is not None]
    valid = [o for o in routed if o.args_valid]
    matched = [o for o in routed if o.args_match]
    print(f"  arguments valid     {len(valid)}/{len(routed)}  (the tool accepts them)")
    print(f"  arguments expected  {len(matched)}/{len(routed)}")
    print(
        f"  invented a tool     {len(invented)}/{len(declines)}  (should have declined)"
    )

    if invented:
        worst = max(o.confidence for o in invented)
        print(f"  worst invented conf {worst:.2f}")
    if correct:
        low = (
            min(o.confidence for o in correct if o.got)
            if any(o.got for o in correct)
            else 0.0
        )
        print(f"  lowest correct conf {low:.2f}")

    slowest = max(o.seconds for o in outcomes)
    median = sorted(o.seconds for o in outcomes)[len(outcomes) // 2]
    print(f"  seconds median {median:.2f}  slowest {slowest:.2f}")

    print("  threshold  refuses-right  runs-wrong")
    for threshold, refused, ran in sweep(outcomes):
        marker = "  <- current" if abs(threshold - 0.7) < 1e-9 else ""
        print(f"    {threshold:>4.1f}     {refused:>10}   {ran:>9}{marker}")

    for outcome in outcomes:
        if not outcome.tool_correct:
            print(
                f"    MISS {outcome.locale:<6} {outcome.id:<28} "
                f"expected {outcome.expected} got {outcome.got} "
                f"({outcome.confidence:.2f}) {outcome.arguments}"
            )

    for outcome in outcomes:
        # Right tool, arguments the tool will refuse: the turn fails as
        # INVALID_ARGUMENTS. Worth seeing, because the fix is usually one line
        # of the tool's description rather than a different model.
        if outcome.tool_correct and outcome.got and not outcome.args_valid:
            print(
                f"    ARGS {outcome.locale:<6} {outcome.id:<28} "
                f"{outcome.got} rejects {outcome.arguments}"
            )


def report_translation(model: str, outcomes: Sequence[TranslationOutcome]) -> None:
    total = len(outcomes)
    print(f"\ntranslation · {model} · {total} cases")
    print(f"  passed              {sum(1 for o in outcomes if o.passed)}/{total}")
    print(f"  echoed the input    {sum(1 for o in outcomes if o.echoed)}/{total}")
    print(
        f"  echoed AND claimed  {sum(1 for o in outcomes if o.claimed_success)}/{total}"
        "  (silent failure)"
    )
    print(
        f"  expected wording    {sum(1 for o in outcomes if o.expected_found)}/{total}"
    )
    print(
        f"  pt-BR leakage       {sum(1 for o in outcomes if o.rejected_found)}/{total}"
    )
    print(f"  identifiers kept    {sum(1 for o in outcomes if o.preserved)}/{total}")

    for outcome in outcomes:
        if not outcome.passed:
            why = []
            if outcome.echoed:
                why.append("echo")
            if not outcome.expected_found:
                why.append("wording")
            if outcome.rejected_found:
                why.append("pt-BR")
            if not outcome.preserved:
                why.append("identifier")
            print(f"    MISS {outcome.id:<28} {','.join(why):<20} {outcome.text!r}")


async def evaluate(model: str, host: str, only: str | None) -> None:
    settings = OllamaSettings(host=host).with_model(model)
    client = OllamaClient(settings)

    registry = build_registry(
        journal=RefusingJournal(),
        confirmation=NeverConfirms(),
        ledger=PermissionLedger(),
        generation=client.bind("generation"),
        # The specs are what is being measured, and `vision.look` is one of
        # them. Nothing here shows it a frame: routing to it is the question,
        # not answering with it.
        frames=Frames(),
        vision=client.bind("vision"),
    )

    if only != "translation":
        router = ModelRouter(client.bind("router"), registry.specs())
        outcomes = [
            await route(router, registry, case)
            for case in cases(ROOT / "model" / "routing.jsonl")
        ]
        report_routing(model, outcomes)

    if only != "routing":
        translations = [
            await translate(client, case)
            for case in cases(ROOT / "translation" / "cases.jsonl")
        ]
        report_translation(model, translations)


async def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E.V. model evals. Not in CI.")
    parser.add_argument("--model", action="append", default=[], metavar="NAME")
    parser.add_argument("--host", default=None)
    parser.add_argument("--only", choices=["routing", "translation"], default=None)
    args = parser.parse_args(argv)

    configured = load_settings(settings_path(default_database_path().parent))
    models = args.model or [configured.router.name]
    host = args.host or configured.host

    for model in models:
        try:
            await evaluate(model, host, args.only)
        except OllamaError as error:
            print(f"\n{model}: {error}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
