"""Orchestration. Never touches the system directly.

This is the generation path with a picture attached: nothing on the machine
changes, a model is asked a question, and the answer is spoken. The camera is
not here -- by the time this runs, a frame has already been captured by a
surface, because a person asked for it.
"""

from __future__ import annotations

from typing import Protocol

from ev.application.frames import Frames
from ev.application.speech import Speaker
from ev.capabilities.vision.args import LookArgs
from ev.domain.results import ToolErrorCode, ToolResult

LOOK = "vision.look"

DESCRIBE = {
    "en": "Describe what you see, in one or two sentences.",
    "pt-PT": "Descreve o que vês, em uma ou duas frases.",
}
"""What to ask when nobody asked anything.

In the locale of the session, because the answer comes back in the language of
the question -- and a vision model given an English instruction answers in
English however it was spoken to.
"""

ANSWER_IN = {
    "en": "Answer in English.",
    "pt-PT": "Responde em português de Portugal.",
}


class Vision(Protocol):
    """What this service needs from a model. Satisfied by `BoundModel`."""

    async def describe(self, prompt: str, image: bytes) -> str: ...


class VisionService:
    def __init__(
        self, frames: Frames, vision: Vision, speaker: Speaker | None = None
    ) -> None:
        self._frames = frames
        self._vision = vision
        self._speaker = speaker or Speaker()

    async def look(self, args: LookArgs) -> ToolResult:
        frame = self._frames.current()
        if frame is None:
            # Nothing turned the camera on, so there is nothing to describe.
            # Saying so is better than a model inventing a room.
            return ToolResult.failure(
                LOOK,
                ToolErrorCode.INVALID_ARGUMENTS,
                self._speaker.say("vision.nothing_to_see"),
            )

        locale = self._speaker.locale
        question = args.question or DESCRIBE.get(locale, DESCRIBE["en"])
        instruction = ANSWER_IN.get(locale, ANSWER_IN["en"])

        answer = await self._vision.describe(f"{question}\n\n{instruction}", frame)
        answer = answer.strip()

        if not answer:
            return ToolResult.failure(
                LOOK, ToolErrorCode.ADAPTER_FAILED, self._speaker.say("vision.nothing")
            )

        # The question is journalled with the call. The frame is not: it is not
        # an argument, and the trail records what was asked, not what was seen.
        return ToolResult.success(LOOK, data={"question": args.question}, speech=answer)
