"""The generation path: the model writes, and nothing it writes selects a target.

There is no `adapters.py` here. This capability's boundary is the model, and
the model already has a port -- `OllamaClient`. Adding an adapter would be a
file that forwards.

A failure returns the original text. Not a guess, not a partial translation,
not silence: the words the user gave, unchanged, with the failure stated.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from ev.capabilities.language.args import TranslateArgs
from ev.domain.results import ToolErrorCode, ToolResult

TRANSLATE = "language.translate"

SYSTEM = """\
You translate text. You do not answer it, explain it, or comment on it.

- Translate into {language}. For pt-PT use European Portuguese, never \
Brazilian: use "tu"/"você" as the source does, and European vocabulary and \
spelling.
- Leave code, URLs, file paths, identifiers, bundle ids and application names \
exactly as they are.
- Keep the formatting, the line breaks and the punctuation of the original.
- If the text is already in the target language, return it unchanged.
- Also report `source`: the language the original is written in, as one of \
pt-PT, en, es, fr, de, it, or other.
"""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        # Asked for in the same call, never a second one. It is what makes an
        # echo detectable: text unchanged is legitimate when the source is
        # already the target, and a silent failure when it is not.
        "source": {"type": "string"},
    },
    "required": ["text", "source"],
}

NAMES = {
    "pt-PT": "European Portuguese (pt-PT)",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
}


class Completion(Protocol):
    """What this capability needs from a model. Satisfied by `OllamaClient`.

    Declared here rather than imported from the router: both consume a model,
    neither owns the other's contract. The signatures match because both
    always constrain the answer with a schema.
    """

    async def complete(
        self, messages: list[dict[str, str]], *, schema: dict[str, Any]
    ) -> str: ...


class LanguageService:
    def __init__(self, completion: Completion) -> None:
        self._completion = completion

    async def translate(self, args: TranslateArgs) -> ToolResult:
        try:
            content = await self._completion.complete(
                [
                    {
                        "role": "system",
                        "content": SYSTEM.format(language=NAMES[args.to]),
                    },
                    {"role": "user", "content": args.text},
                ],
                schema=SCHEMA,
            )
            payload = json.loads(content)
            translated = payload["text"]
            if not isinstance(translated, str) or not translated.strip():
                raise ValueError("the model returned no text")

            source = str(payload.get("source", "")).casefold()
            if translated.strip() == args.text.strip() and source != args.to.casefold():
                # Measured on two models: both hand back the input unchanged on
                # some inputs, and without this the caller cannot tell that
                # from a legitimate no-op. Reporting success here would be the
                # failure that looks like a success.
                raise ValueError(
                    f"the model returned the text unchanged, and reports it is "
                    f"written in {source or 'an unknown language'}"
                )
        except Exception as error:
            # Caught here rather than left to the registry, because the
            # contract is specific: a translation failure gives back what the
            # user said. Losing their words to report an error is worse than
            # the error.
            return ToolResult.failure(
                TRANSLATE,
                ToolErrorCode.ADAPTER_FAILED,
                f"could not translate: {error}",
                data={"text": args.text, "translated": False},
            )

        return ToolResult.success(
            TRANSLATE,
            data={"text": translated, "to": args.to, "translated": True},
            speech=translated,
        )
