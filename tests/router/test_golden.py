"""The golden routing cases in `evals/routing/`.

These are deterministic -- no weights, no network -- so they run in the suite.
A change that moves a case fails here, which is the point: it becomes a diff
someone chose rather than drift nobody noticed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

from ev.router.static import StaticRouter

EVALS = Path(__file__).resolve().parents[2] / "evals" / "routing"
LOCALES = {"en", "pt-PT"}


def cases() -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for path in sorted(EVALS.glob("*.jsonl")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                case = json.loads(line)
                case["source"] = f"{path.name}:{number}"
                loaded.append(case)
    return loaded


ALL = cases()


def test_there_are_cases() -> None:
    # A glob that matches nothing would make every test below vacuous.
    assert ALL


@pytest.mark.parametrize("case", ALL, ids=lambda case: f"{case['source']}")
def test_golden_case(case: dict[str, Any]) -> None:
    resolution = StaticRouter().resolve(case["utterance"])

    if case["tool"] is None:
        assert resolution is None, (
            f"{case['utterance']!r} must fall through to the model router, "
            f"but tier 1 answered with {resolution!r}"
        )
        return

    assert resolution is not None, f"{case['utterance']!r} was not routed"
    assert resolution.tool == case["tool"]
    assert resolution.arguments == case["arguments"]
    assert resolution.confidence == 1.0


def test_every_intent_exists_in_both_languages() -> None:
    # Tool calling degrades in non-English. Pairing the cases is what makes
    # that measurable instead of assumed.
    locales: dict[str, set[str]] = defaultdict(set)
    for case in ALL:
        locales[case["id"]].add(case["locale"])

    unpaired = {name: sorted(seen) for name, seen in locales.items() if seen != LOCALES}

    assert unpaired == {}


def test_locales_are_european_portuguese() -> None:
    # pt-PT, never pt-BR: multilingual models default to Brazilian, and the
    # cases are where that drift gets caught.
    assert {case["locale"] for case in ALL} <= LOCALES
