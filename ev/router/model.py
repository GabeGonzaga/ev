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
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
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
- response must be null when you are calling a tool. Do not narrate the call: \
E.V. says what happened after it happens. Write a response only when you are \
unsure and need to ask the user something, and then write it in the language \
of the request.

Tools:
"""


TODAY = "Now: {now} ({weekday}). Tomorrow: {tomorrow}. Write dates in exactly \
that format -- ISO 8601 local time, no timezone. Never write a date earlier \
than now."
"""A second system message, not part of the first one.

A tool takes a date now, and "amanhã às nove" cannot be turned into one by a
model that does not know what day it is. It is separate for two reasons: the
tool list is identical on every turn and Ollama caches that prefix, and a
daemon that has been up for two days would otherwise still be telling the
model it is Monday.

The date is written in the format the answer must use, which is worth more
than any wording. Measured against qwen3:8b, with the same six utterances each
time: prose ("Today is Wednesday, 12 August 2026") put "amanhã às nove" a day
late in Portuguese and right in English; the same fact as an ISO stamp did not.
Tomorrow is spelled out rather than left as arithmetic for the same reason.

What this does not fix: "on the 1st", when the 1st has passed, resolves to
this month rather than next. A sentence spelling that rule out was tried and
made it worse -- the English case went back to writing a date in the past. The
service refuses a past date and says so, which is the honest end of it, and
"tomorrow", "tonight" and "in two hours" are the phrasings that actually
matter and all measure correct.
"""


def _now() -> datetime:
    return datetime.now()


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
        self,
        completion: Completion,
        specs: Sequence[Mapping[str, Any]],
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._completion = completion
        self._clock = clock
        self._specs = list(specs)
        self._names = [str(spec.get("function", spec)["name"]) for spec in self._specs]
        # Built once: the registry does not change after startup, and this is
        # on the turn path.
        self._schema = resolution_schema(self._names)
        self._system = system_prompt(self._specs)

    async def resolve(self, utterance: str) -> Resolution | None:
        if not self._names:
            return None

        now = self._clock()
        content = await self._completion.complete(
            [
                {"role": "system", "content": self._system},
                # After the stable prefix and before the utterance, which
                # reaches the model verbatim -- prefixing the user's own words
                # with context would change the request it is reading.
                {
                    "role": "system",
                    "content": TODAY.format(
                        now=now.strftime("%Y-%m-%dT%H:%M"),
                        weekday=now.strftime("%A"),
                        tomorrow=(now + timedelta(days=1)).strftime("%Y-%m-%d"),
                    ),
                },
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
