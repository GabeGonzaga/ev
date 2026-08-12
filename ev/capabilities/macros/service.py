"""Running a macro: the same door, once per step.

A macro is not a way around anything. Each step goes through
`Registry.call()` exactly as if it had been spoken -- validated against the
tool's args model, checked by the policy, confirmed if destructive, and
journalled on its own line. A macro that could skip any of that would be a
shell with a friendly name.

It stops at the first failure. Continuing would mean a macro whose later steps
run against a state its earlier steps failed to create, and reporting "3 of 5
worked" is more useful than guessing which of those five mattered.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ev.application.speech import Speaker
from ev.capabilities.macros.args import RunArgs
from ev.domain.macro import Macro
from ev.domain.results import ToolErrorCode, ToolResult

RUN = "macro.run"

Macros = Callable[[], Mapping[str, Macro]]
"""Read each time rather than held: a macro edited in an editor should run on
the next turn, the same reason permission grants are re-read."""

Caller = Callable[[str, Mapping[str, object]], Any]
"""`Registry.call`. Named as a port so this capability does not reach into the
registry for anything else."""


class MacroService:
    def __init__(
        self, macros: Macros, call: Caller, speaker: Speaker | None = None
    ) -> None:
        self._macros = macros
        self._call = call
        self._speaker = speaker or Speaker()

    async def run(self, args: RunArgs) -> ToolResult:
        available = self._macros()
        macro = available.get(args.name.casefold())

        if macro is None:
            known = ", ".join(sorted(m.name for m in available.values())) or "none"
            return ToolResult.failure(
                RUN,
                ToolErrorCode.INVALID_ARGUMENTS,
                self._speaker.say("macro.unknown", name=args.name, existing=known),
            )

        done: list[str] = []
        for number, step in enumerate(macro.steps, start=1):
            result: ToolResult = await self._call(step.tool, step.arguments)

            if not result.ok:
                # Which step, and why. "The macro failed" is not something
                # anyone can act on.
                why = result.error.message if result.error else "no reason given"
                return ToolResult.failure(
                    RUN,
                    result.error.code if result.error else ToolErrorCode.ADAPTER_FAILED,
                    self._speaker.say(
                        "macro.stopped",
                        name=macro.name,
                        step=number,
                        tool=step.tool,
                        why=why,
                    ),
                    data={"macro": macro.name, "completed": done, "failed_at": number},
                )

            done.append(step.tool)

        return ToolResult.success(
            RUN,
            data={"macro": macro.name, "completed": done},
            speech=self._speaker.say("macro.ran", name=macro.name, steps=len(done)),
        )
