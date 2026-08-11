"""Saying something out loud.

The core depends on `SpeechSynthesizer`, never on an engine. Two
implementations exist for two situations, and the difference is who owns the
audio device:

* `SaySynthesizer` speaks here, through `say(1)`. It is for development and
  for the CLI, where the process in front of the user is this one.
* The daemon does not speak at all. It emits `speech.requested` and the native
  host speaks, because the audio device belongs to the signed process. That
  event *is* this interface's other implementation, and it lives at the socket
  rather than in a class here.

`say` is the development engine; `AVSpeechSynthesizer` replaces it in the
application, on the native side. Nothing in the core changes when it does.
"""

from __future__ import annotations

from typing import Protocol

from ev.infrastructure.macos.processes import ProcessFailed, ProcessRunner

SAY_TIMEOUT = 30.0

VOICES = {
    # pt-PT, not pt-BR. Joana is the European voice; without naming her, macOS
    # picks by system language and a Portuguese sentence gets read by whatever
    # is default, which is usually Brazilian or English.
    "pt-PT": "Joana",
}


class SpeechSynthesizer(Protocol):
    async def speak(self, text: str, *, voice: str | None = None) -> None: ...


class SaySynthesizer:
    """`say(1)`. Development only, and only where this process owns the audio."""

    def __init__(self, processes: ProcessRunner) -> None:
        self._processes = processes

    async def speak(self, text: str, *, voice: str | None = None) -> None:
        argv = ["say"]

        named = VOICES.get(voice or "")
        if named is not None:
            argv += ["-v", named]

        # "--" ends option parsing: a sentence beginning with "-" is a
        # sentence, not a flag. The text is the user's or the model's, so it
        # is never trusted to be flag-shaped.
        argv += ["--", text]

        try:
            await self._processes.run(argv, timeout=SAY_TIMEOUT)
        except ProcessFailed:
            # Not being able to speak is not a reason to fail a turn that
            # already happened. The words are on screen either way.
            return
