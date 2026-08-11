"""Tier 2. What the static router did not recognise.

The model proposes; it does not decide. What comes back here is a `Resolution`
-- the same type tier 0 and tier 1 produce -- and it goes through exactly the
same validation, policy and confirmation afterwards. Nothing about this file
gives the model authority it did not have.

Three things constrain the answer before it is even generated:

* `tool` is an enum of the registered names, or null. The model cannot invent
  a tool, and it has a way to say "none of these" other than guessing.
* `confidence` is bounded in the schema, not clamped afterwards.
* The whole object is decoded against a JSON Schema, so malformed output is
  unlikely -- and validated anyway, because unlikely is not impossible.

`arguments` is deliberately left as a free object here. The tool's own args
model is what validates it, at the one door, and duplicating those schemas into
the decoding grammar would mean two definitions of the same contract.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import ValidationError

from ev.domain.resolution import Resolution

SYSTEM = """\
You turn a request into one tool call, or into nothing.

Rules:
- Reply only with the JSON object the schema requires.
- Use a tool name exactly as listed below. If none of them does what was \
asked, set tool to null.
- Copy names, titles, paths and identifiers from the request exactly as \
written. Never translate, correct, expand or capitalise them. The words the \
user chose are the arguments.
- confidence is how certain you are, from 0 to 1. Use 1.0 only when the \
request plainly matches one tool and every argument is present. Use less than \
0.5 when you are guessing.
- response is one short sentence in the same language as the request, or null.

Tools:
"""


class Completion(Protocol):
    """What this router needs from a model. Satisfied by `OllamaClient`."""

    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any]
    ) -> str: ...


def resolution_schema(names: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            # null is how the model declines. Without it, being forced to name
            # a tool turns "I do not know" into a confident wrong answer.
            "tool": {"type": ["string", "null"], "enum": [*names, None]},
            "arguments": {"type": "object"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "response": {"type": ["string", "null"]},
        },
        "required": ["tool", "arguments", "confidence"],
    }


def system_prompt(specs: Sequence[Mapping[str, Any]]) -> str:
    # Compact, because every token here is latency on the turn path.
    listed = "\n".join(
        json.dumps(spec.get("function", spec), separators=(",", ":"), sort_keys=True)
        for spec in specs
    )
    return SYSTEM + listed


class ModelRouter:
    def __init__(
        self, completion: Completion, specs: Sequence[Mapping[str, Any]]
    ) -> None:
        self._completion = completion
        self._specs = list(specs)
        self._names = [str(spec.get("function", spec)["name"]) for spec in self._specs]
        # Built once: the registry does not change after startup, and this is
        # on the turn path.
        self._schema = resolution_schema(self._names)
        self._system = system_prompt(self._specs)

    async def resolve(self, utterance: str) -> Resolution | None:
        if not self._names:
            return None

        content = await self._completion.complete(
            [
                {"role": "system", "content": self._system},
                {"role": "user", "content": utterance},
            ],
            schema=self._schema,
        )

        return self._parse(content)

    def _parse(self, content: str) -> Resolution | None:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            # Constrained decoding makes this unlikely. Unlikely is not never,
            # and a half-parsed action is worse than no action.
            return None

        if not isinstance(payload, dict) or payload.get("tool") is None:
            return None

        try:
            resolution = Resolution.model_validate(payload)
        except ValidationError:
            return None

        if resolution.tool not in self._names:
            # The enum should have prevented this. Checked anyway: the registry
            # would refuse it, but refusing here keeps an invented name out of
            # the journal and out of the confidence numbers.
            return None

        return resolution
