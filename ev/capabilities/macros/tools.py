"""Registry entries. Declaration only, no logic."""

from __future__ import annotations

from typing import Any

from ev.capabilities.macros.args import RunArgs
from ev.capabilities.macros.service import RUN, MacroService
from ev.domain.risk import RiskLevel
from ev.registry import ToolSpec


def macro_tools(service: MacroService) -> tuple[ToolSpec[Any], ...]:
    return (
        ToolSpec(
            name=RUN,
            description=(
                "Run a macro: a saved list of tool calls, by name. Each step is "
                "checked and confirmed exactly as if it had been asked for "
                "directly."
            ),
            args=RunArgs,
            risk=RiskLevel.SAFE,
            handler=service.run,
            # None of its own. Every step is gated on its own permissions when
            # it runs, so claiming them here would grant a macro more than the
            # sum of what it does.
            permissions=frozenset(),
        ),
    )
