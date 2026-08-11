"""Turning recorded speech into text.

The core depends on `SpeechRecognizer`, never on whisper. `whisper.cpp` is the
engine today; `SFSpeechRecognizer` is a fallback backend at most, and neither
name appears above this file.

Two rules from `CLAUDE.md` are enforced here rather than hoped for:

* **The language is always stated.** Auto-detect is unreliable on the
  sub-two-second utterances that are the normal case, and a misdetected
  language produces confident text in the wrong one -- a failure that reads
  like a success, and one that then becomes a tool argument.
* **The model is `small`, multilingual.** Real input is mixed: "abre o Visual
  Studio Code" is neither language cleanly, and `base` handles that badly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from ev.infrastructure.macos.processes import ProcessFailed, ProcessRunner

WHISPER_TIMEOUT = 60.0
DEFAULT_MODEL = Path(__file__).resolve().parents[3] / "models" / "ggml-small.bin"

# whisper.cpp takes a two-letter code; the session carries a full tag.
LANGUAGES = {
    "pt-PT": "pt",
    "pt": "pt",
    "en": "en",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "it": "it",
}

_BRACKETED = re.compile(r"\[[^\]]*\]|\([^)]*\)")
"""whisper emits [BLANK_AUDIO], (wind blowing) and similar. They are
descriptions of the recording, not things the user said."""


class Transcription(Exception):
    """Nothing usable came back. Never a guess."""


class SpeechRecognizer(Protocol):
    async def transcribe(self, audio: Path, *, language: str) -> str: ...


def language_code(language: str) -> str:
    code = LANGUAGES.get(language)
    if code is None:
        known = ", ".join(sorted(LANGUAGES))
        raise Transcription(f"unknown language {language!r}. Known: {known}")
    return code


def clean(output: str) -> str:
    """What the user said, without whisper's annotations."""
    text = _BRACKETED.sub(" ", output)
    return " ".join(text.split())


class WhisperCppRecognizer:
    def __init__(
        self,
        processes: ProcessRunner,
        *,
        model: Path = DEFAULT_MODEL,
        threads: int = 4,
    ) -> None:
        self._processes = processes
        self._model = model
        self._threads = threads

    async def transcribe(self, audio: Path, *, language: str) -> str:
        if not self._model.exists():
            raise Transcription(f"no model at {self._model}. Run: make models")

        argv = [
            "whisper-cli",
            "--model",
            str(self._model),
            # Stated, never 'auto'. This is the whole point of carrying a
            # locale on the session.
            "--language",
            language_code(language),
            "--threads",
            str(self._threads),
            "--no-timestamps",
            "--no-prints",
            "--file",
            str(audio),
        ]

        try:
            completed = await self._processes.run(argv, timeout=WHISPER_TIMEOUT)
        except ProcessFailed as failure:
            raise Transcription(str(failure)) from failure

        text = clean(completed.stdout)
        if not text:
            # Silence, or a room. Either way there is nothing to route, and
            # inventing something would be worse than saying so.
            raise Transcription("nothing was said")

        return text
