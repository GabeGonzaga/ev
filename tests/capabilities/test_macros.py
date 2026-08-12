"""Macros: a saved list of calls that goes through the same door as speech."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from ev.capabilities.macros.args import RunArgs
from ev.capabilities.macros.service import MacroService
from ev.capabilities.macros.tools import macro_tools
from ev.domain.macro import Macro, MacroStep
from ev.domain.results import ToolErrorCode, ToolResult
from ev.domain.risk import RiskLevel
from ev.infrastructure.macros import load_macros, macros_path, save_macros


class Door:
    """Stands in for Registry.call, and records what went through it."""

    def __init__(self, *, fails_at: int | None = None) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._fails_at = fails_at

    async def __call__(self, tool: str, arguments: Mapping[str, object]) -> ToolResult:
        self.calls.append((tool, dict(arguments)))
        if self._fails_at == len(self.calls):
            return ToolResult.failure(
                tool, ToolErrorCode.PERMISSION_DENIED, "needs apple_events"
            )
        return ToolResult.success(tool)


def morning() -> Macro:
    return Macro(
        name="morning",
        description="the usual",
        steps=[
            MacroStep(tool="browser.open_url", arguments={"url": "https://a.test"}),
            MacroStep(tool="music.play", arguments={"name": "Blonde", "kind": "album"}),
        ],
    )


def service(door: Door, *macros: Macro) -> MacroService:
    by_name = {macro.name.casefold(): macro for macro in macros}
    return MacroService(lambda: by_name, door)


# --- running --------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_step_goes_through_the_same_door() -> None:
    # A macro is not a way around the registry. Each step is validated,
    # policed, confirmed and journalled exactly as if it had been spoken.
    door = Door()

    result = await service(door, morning()).run(RunArgs(name="morning"))

    assert result.ok
    assert door.calls == [
        ("browser.open_url", {"url": "https://a.test"}),
        ("music.play", {"name": "Blonde", "kind": "album"}),
    ]
    assert result.speech == "Ran morning: 2 steps"


@pytest.mark.asyncio
async def test_it_stops_at_the_first_failure() -> None:
    # Later steps would run against a state the earlier one failed to create.
    door = Door(fails_at=1)

    result = await service(door, morning()).run(RunArgs(name="morning"))

    assert not result.ok
    assert len(door.calls) == 1, "the second step did not run"
    assert result.error is not None
    assert result.error.code is ToolErrorCode.PERMISSION_DENIED


@pytest.mark.asyncio
async def test_a_failure_says_which_step_and_why() -> None:
    # "The macro failed" is not something anyone can act on.
    door = Door(fails_at=2)

    result = await service(door, morning()).run(RunArgs(name="morning"))

    assert result.error is not None
    assert "step 2" in result.error.message
    assert "music.play" in result.error.message
    assert "needs apple_events" in result.error.message
    assert result.data["completed"] == ["browser.open_url"]
    assert result.data["failed_at"] == 2


@pytest.mark.asyncio
async def test_an_unknown_macro_names_the_ones_that_exist() -> None:
    door = Door()

    result = await service(door, morning()).run(RunArgs(name="evening"))

    assert not result.ok
    assert result.error is not None
    assert "morning" in result.error.message
    assert door.calls == []


@pytest.mark.asyncio
async def test_the_name_is_matched_without_case() -> None:
    door = Door()

    result = await service(door, morning()).run(RunArgs(name="MORNING"))

    assert result.ok


def test_running_a_macro_claims_no_permissions_of_its_own() -> None:
    # Every step is gated when it runs. Claiming permissions here would grant
    # a macro more than the sum of what it does.
    (spec,) = macro_tools(service(Door()))

    assert spec.permissions == frozenset()
    assert spec.risk is RiskLevel.SAFE


# --- the file -------------------------------------------------------------


def test_macros_round_trip(tmp_path: Path) -> None:
    path = macros_path(tmp_path)

    save_macros(path, [morning()])

    assert load_macros(path)["morning"] == morning()


def test_no_file_means_no_macros(tmp_path: Path) -> None:
    assert load_macros(macros_path(tmp_path)) == {}


def test_two_macros_with_one_name_are_refused(tmp_path: Path) -> None:
    # A question nobody can answer at run time, answered here instead.
    path = macros_path(tmp_path)
    path.write_text(
        json.dumps(
            [
                json.loads(morning().model_dump_json()),
                json.loads(morning().model_dump_json()),
            ]
        )
    )

    with pytest.raises(ValueError, match="two macros are called"):
        load_macros(path)


def test_a_macro_with_no_steps_is_not_a_macro() -> None:
    with pytest.raises(ValidationError):
        Macro(name="empty", steps=[])


def test_a_step_cannot_carry_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        MacroStep.model_validate(
            {"tool": "browser.open_url", "arguments": {}, "retries": 3}
        )
